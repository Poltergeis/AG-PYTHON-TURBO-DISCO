import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
import json
from dataclasses import dataclass, field, asdict
from typing import TypedDict, Any, Callable
import math
from enum import Enum, auto
import statistics
import random
import copy

# --- Enums y Utilidades ---

class TipoMutacion(Enum):
    CAMBIO_DE_POSICIONES = auto()
    CAMBIO_DE_ID = auto()

# --- Estructuras de Datos ---

@dataclass
class Participante:
    nombre: str | None
    peso_kg: float
    id: str

@dataclass
class Individuo:
    nombre: str | None
    posiciones: list[str] # Lista de IDs
    generacion: int
    aptitud: float | None = None
    
    def to_dict(self):
        return {
            "nombre": self.nombre,
            "posiciones": self.posiciones,
            "generacion": self.generacion,
            "aptitud": self.aptitud
        }

@dataclass
class ParejaRegistro:
    padres_ids: tuple[str, str] # Guardamos solo IDs o Nombres para no serializar objetos completos
    individuos_resultantes: list[Individuo]
    
    def to_dict(self):
        return {
            "padres": self.padres_ids,
            "hijos": [h.to_dict() for h in self.individuos_resultantes]
        }

@dataclass
class MutacionRegistro:
    individuo_id: str # ID o nombre del individuo que mutó
    tipo_mutacion: str
    generacion: int
    
    def to_dict(self):
        return {
            "individuo_id": self.individuo_id,
            "tipo_mutacion": self.tipo_mutacion,
            "generacion": self.generacion
        }

@dataclass
class Generacion:
    numero: int
    poblacion: list[Individuo]
    mejor_individuo: Individuo
    peor_individuo: Individuo
    aptitud_promedio: float
    desviacion_torque: float
    
    def to_dict(self):
        return {
            "numero": self.numero,
            "poblacion": [ind.to_dict() for ind in self.poblacion],
            "mejor_individuo": self.mejor_individuo.to_dict(),
            "peor_individuo": self.peor_individuo.to_dict(),
            "aptitud_promedio": self.aptitud_promedio,
            "desviacion_torque": self.desviacion_torque
        }

@dataclass
class Resultado:
    mejor_global: Individuo | None
    configuracion: dict
    generaciones: list[Generacion] = field(default_factory=list)
    
    def to_dict(self):
        return {
            "mejor_global": self.mejor_global.to_dict() if self.mejor_global else None,
            "configuracion": self.configuracion,
            "generaciones": [g.to_dict() for g in self.generaciones]
        }

class ParticipanteDictPattern(TypedDict):
    nombre: str | None
    id: str
    peso_kg: float

class RunAgEventBody(TypedDict):
    poblacion_maxima: int
    poblacion_inicial_size: int | None
    participantes: list[ParticipanteDictPattern]
    num_asientos: int
    num_generaciones: int
    umbral_cruza: float # 0.0 a 1.0
    umbral_mutacion: float # Probabilidad de que un individuo mute
    # Probabilidad relativa entre tipos de mutación (deben sumar 1.0 idealmente o se normalizan)
    prob_mutacion_cambio_id: float 
    prob_mutacion_cambio_pos: float 

# --- Lógica del Algoritmo Genético ---

class AlgoritmoGeneticoTorque:
    def __init__(self, data: RunAgEventBody):
        self.config = data
        self.participantes = [Participante(**p) for p in data["participantes"]]
        self.todos_los_ids = set(p.id for p in self.participantes)
        # Mapa O(1) para buscar pesos
        self.mapa_pesos = {p.id: p.peso_kg for p in self.participantes}
        
        # Validaciones iniciales
        if self.config["poblacion_inicial_size"] is None:
            self.config["poblacion_inicial_size"] = max(2, int(self.config["poblacion_maxima"] * 0.7))
        
        # Pre-calcular multiplicadores de torque (Brazos de palanca)
        # Centro geométrico: (N - 1) / 2. 
        # Ejemplo 5 asientos: indices 0,1,2,3,4. Centro = 2. Multiplicadores: -2, -1, 0, 1, 2
        # Ejemplo 4 asientos: indices 0,1,2,3. Centro = 1.5. Multiplicadores: -1.5, -0.5, 0.5, 1.5
        n = self.config["num_asientos"]
        centro = (n - 1) / 2
        self.multiplicadores = [i - centro for i in range(n)]

    def generar_poblacion_inicial(self) -> list[Individuo]:
        poblacion = []
        ids_list = list(self.todos_los_ids)
        num_asientos = self.config["num_asientos"]
        
        for i in range(self.config["poblacion_inicial_size"]):
            # Random.sample elige elementos únicos sin repetición para ese individuo
            posiciones = random.sample(ids_list, num_asientos)
            ind = Individuo(
                nombre=f"Gen0-{i}",
                posiciones=posiciones,
                generacion=0,
                aptitud=None
            )
            poblacion.append(ind)
        return poblacion

    def evaluar_aptitud(self, individuo: Individuo):
        if individuo.aptitud is not None:
            return

        torque_total = 0.0
        # Uso de zip y mapa de pesos para máxima velocidad
        for id_part, multiplicador in zip(individuo.posiciones, self.multiplicadores):
            peso = self.mapa_pesos[id_part]
            torque_total += peso * multiplicador
        
        individuo.aptitud = torque_total

    def cruzar(self, padre: Individuo, madre: Individuo, num_gen: int) -> list[Individuo]:
        # Cruza: 1 del padre, 1 de la madre...
        n_asientos = len(padre.posiciones)
        hijo1_pos = [None] * n_asientos
        hijo2_pos = [None] * n_asientos
        
        # Llenado alternado
        for i in range(n_asientos):
            if i % 2 == 0: # Pares: Padre
                hijo1_pos[i] = padre.posiciones[i]
                hijo2_pos[i] = madre.posiciones[i]
            else: # Impares: Madre
                hijo1_pos[i] = madre.posiciones[i]
                hijo2_pos[i] = padre.posiciones[i]
        
        # Reparación de duplicados y asignación de faltantes
        self._reparar_genoma(hijo1_pos)
        self._reparar_genoma(hijo2_pos)
        
        h1 = Individuo(f"G{num_gen}-H1", hijo1_pos, num_gen)
        h2 = Individuo(f"G{num_gen}-H2", hijo2_pos, num_gen)
        
        return [h1, h2]

    def _reparar_genoma(self, posiciones: list[str]):
        """
        Elimina duplicados y rellena con IDs disponibles del pool total.
        Modifica la lista in-place.
        """
        usados = set()
        duplicados_indices = []
        
        # Detectar duplicados
        for idx, id_p in enumerate(posiciones):
            if id_p in usados:
                duplicados_indices.append(idx)
            else:
                usados.add(id_p)
        
        if not duplicados_indices:
            return

        # Buscar disponibles (Total - Usados)
        disponibles = list(self.todos_los_ids - usados)
        random.shuffle(disponibles)
        
        # Reemplazar duplicados con disponibles
        for idx in duplicados_indices:
            if disponibles:
                nuevo_id = disponibles.pop()
                posiciones[idx] = nuevo_id
                usados.add(nuevo_id)
            else:
                # Caso extremo: no hay más participantes disponibles (N_asientos == N_participantes)
                # Esto no debería pasar si la lógica de conjuntos es correcta, 
                # a menos que haya un error lógico previo.
                pass

    def mutar(self, individuo: Individuo) -> str | None:
        """ Aplica mutación según probabilidades y retorna el tipo aplicado o None """
        if random.random() > self.config["umbral_mutacion"]:
            return None

        # Ponderación de tipos de mutación
        peso_id = self.config["prob_mutacion_cambio_id"]
        peso_pos = self.config["prob_mutacion_cambio_pos"]
        total_peso = peso_id + peso_pos
        
        r = random.uniform(0, total_peso)
        
        if r < peso_id:
            # Tipo 1: Cambio de ID (Traer a alguien de la banca)
            ids_actuales = set(individuo.posiciones)
            ids_banca = list(self.todos_los_ids - ids_actuales)
            
            if ids_banca: # Solo si hay gente en banca
                pos_a_cambiar = random.randint(0, len(individuo.posiciones) - 1)
                nuevo_id = random.choice(ids_banca)
                individuo.posiciones[pos_a_cambiar] = nuevo_id
                return "CAMBIO_DE_ID"
            else:
                # Si no hay banca, forzamos cambio de posición
                pass
        
        # Tipo 2: Intercambio de posición (Swap)
        idx1, idx2 = random.sample(range(len(individuo.posiciones)), 2)
        individuo.posiciones[idx1], individuo.posiciones[idx2] = individuo.posiciones[idx2], individuo.posiciones[idx1]
        return "CAMBIO_DE_POSICIONES"

    def poda(self, poblacion: list[Individuo]) -> list[Individuo]:
        # Objetivo: Aptitud (Torque) cercana a 0.
        # Ordenamos por valor absoluto de la aptitud.
        poblacion.sort(key=lambda x: abs(x.aptitud if x.aptitud is not None else float('inf')))
        return poblacion[:self.config["poblacion_maxima"]]

    def ejecutar(self) -> Resultado:
        poblacion = self.generar_poblacion_inicial()
        registro_generaciones = []
        
        # Evaluación inicial
        for ind in poblacion:
            self.evaluar_aptitud(ind)
            
        # Poda inicial para ordenar
        poblacion = self.poda(poblacion) 

        for gen_i in range(1, self.config["num_generaciones"] + 1):
            nueva_poblacion = []
            
            # --- Elitismo ---
            # Conservamos al mejor tal cual
            if poblacion:
                mejor = copy.deepcopy(poblacion[0])
                mejor.generacion = gen_i
                mejor.nombre = f"Elite-G{gen_i}"
                nueva_poblacion.append(mejor)

            # --- Cruza ---
            # Seleccionamos parejas al azar de la población actual (Tournament o Random simple)
            while len(nueva_poblacion) < self.config["poblacion_maxima"]:
                if len(poblacion) < 2: break
                
                # Selección simple: tomar 2 al azar de los mejores 50%
                pool_padres = poblacion[:max(2, int(len(poblacion)/2))]
                padre, madre = random.sample(pool_padres, 2)
                
                if random.random() <= self.config["umbral_cruza"]:
                    hijos = self.cruzar(padre, madre, gen_i)
                    nueva_poblacion.extend(hijos)
                
            # --- Mutación ---
            for ind in nueva_poblacion:
                # No mutamos al Elite para no perder la mejor solución
                if "Elite" in (ind.nombre or ""):
                    continue
                self.mutar(ind)
                
            # --- Evaluación ---
            for ind in nueva_poblacion:
                self.evaluar_aptitud(ind)
                
            # --- Unión y Poda (Selección Natural) ---
            # Unimos hijos con padres para asegurar que la calidad no baje (Steady State / Generational overlap)
            # O reemplazamos completamente. Aquí usaremos reemplazo + elitismo (ya incluido arriba)
            # Pero para garantizar convergencia, a veces es bueno mezclar y podar.
            poblacion_mixta = poblacion + nueva_poblacion
            
            # Eliminar duplicados exactos de configuración para mantener diversidad (opcional, pero recomendado)
            # Usamos una tupla de posiciones como clave
            unicos = {}
            for p in poblacion_mixta:
                key = tuple(p.posiciones)
                if key not in unicos:
                    unicos[key] = p
            
            poblacion_mixta = list(unicos.values())
            
            # Poda final de la generación
            poblacion = self.poda(poblacion_mixta)
            
            # --- Estadísticas ---
            aptitudes = [ind.aptitud for ind in poblacion if ind.aptitud is not None]
            
            stats_gen = Generacion(
                numero=gen_i,
                poblacion=copy.deepcopy(poblacion), # Copia para el historial
                mejor_individuo=copy.deepcopy(poblacion[0]),
                peor_individuo=copy.deepcopy(poblacion[-1]),
                aptitud_promedio=statistics.fmean(aptitudes) if aptitudes else 0.0,
                desviacion_torque=statistics.stdev(aptitudes) if len(aptitudes) > 1 else 0.0
            )
            registro_generaciones.append(stats_gen)

        mejor_global = poblacion[0] if poblacion else None
        
        return Resultado(
            mejor_global=mejor_global,
            configuracion=self.config,
            generaciones=registro_generaciones
        )

# --- FastAPI Setup ---

app = FastAPI()

def run_ag_logic(data: RunAgEventBody):
    # Instanciamos la clase del algoritmo
    ag = AlgoritmoGeneticoTorque(data)
    # Ejecutamos
    resultado = ag.ejecutar()
    # Retornamos dict puro
    return resultado.to_dict()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data_text = await ws.receive_text()
            message = json.loads(data_text)
            
            event_name = message.get("event_name")
            event_data = message.get("event_data")
            
            if event_name == "run_ag":
                # Procesamiento síncrono (bloqueante) ya que la salida es directa al final
                # Si el cálculo es muy pesado, se debería usar run_in_executor
                resultado = run_ag_logic(event_data)
                
                response = {
                    "event_name": "ag_completed",
                    "data": resultado
                }
                await ws.send_text(json.dumps(response))
                
    except WebSocketDisconnect:
        print("Cliente desconectado")
    except Exception as e:
        print(f"Error: {e}")
        await ws.send_text(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)