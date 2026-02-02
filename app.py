from dataclasses import dataclass
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
import json
from typing import TypedDict, Any, Callable, TypeVar
import math
from enum import Enum, auto
from collections import defaultdict

class CruzaGenTurno(Enum):
  PADRE = auto()
  MADRE = auto()
  
class TipoMutacion(Enum):
  CAMBIO_DE_POSICIONES = auto()
  CAMBIO_DE_ID = auto()

T = TypeVar("T")
def distribucion_uniforme(lista: list[T]) -> T:
  u = np.random.uniform()
  distribucion = 1 / len(lista)
  index = round(u / distribucion)
  return lista[index]

def distribucion_uniforme_ponderada(items: list[tuple[T, float]]) -> T:
  u = np.random.uniform()
  total_peso = sum(peso for _, peso in items)
  acumulado = 0.0
  for valor, peso in items:
    acumulado += peso / total_peso
    if u <= acumulado:
      return valor
  
  return items[-1][0]
  

@dataclass
class Participante:
  nombre: str | None = None
  peso_kg: float
  id: str

@dataclass
class Individuo:
  nombre: str | None = None
  posiciones: list[str]
  generacion: int
  aptitud: float | None
  
@dataclass
class ParejaRegistro:
  individuos: tuple[Individuo, Individuo]
  individuos_resultantes: list[Individuo]
  generacion: int
  probabilidad_calculada: float

@dataclass
class MutacionRegistro:
  individuo_old: Individuo
  individuo_new: Individuo
  probabilidad_calculada: float
  tipo_mutacion: str
  tipo_mutacion_probabilidad: float

@dataclass
class Generacion:
  numero: int
  mejor_individuo: Individuo
  peor_individuo: Individuo
  aptitud_promedio: float
  parejas: list[ParejaRegistro]
  mutaciones: list[MutacionRegistro]
  
@dataclass
class Resultado:
  mejor_individuo: Individuo
  peor_individuo: Individuo
  promedio_aptitud: Individuo
  generaciones: list[Generacion]

class ParticipanteDictPattern(TypedDict):
  nombre: str | None
  id: str
  peso_kg: float

class RunAgEventBody(TypedDict):
  poblacion_maxima: int
  poblacion_inicial_size: int | None
  participantes:list[ParticipanteDictPattern]
  num_asientos: int
  num_generaciones: int

OutFunc = Callable[[str], None]

def handle_event(event_name:str, event_data: Any, out:OutFunc):
  match event_name:
    case "run_ag":
      run_ag(event_data, out)
      
def parse_participantes(event_data: RunAgEventBody):
  participantes: list[Participante] = []
  for p in event_data["participantes"]:
    participantes.append(
      Participante(
        nombre=p["nombre"], peso_kg=p["peso_kg"], id=p["id"]
      )
    )
  return participantes

def resolve_missing(event_data: RunAgEventBody):
  if event_data["poblacion_inicial_size"] is None:
    event_data["poblacion_inicial_size"] = int(event_data["poblacion_maxima"] * 0.7)
    if event_data["poblacion_inicial_size"] == 0:
      event_data["poblacion_inicial_size"] = 1


def generar_individuo_recursive(individuo_ref: Individuo, participantes_disponibles: list[str], asientos_restantes: int):
  if asientos_restantes > 0:
    id_seleccionada = distribucion_uniforme(participantes_disponibles)
    individuo_ref.posiciones[asientos_restantes] = id_seleccionada
    participantes_disponibles.remove(id_seleccionada)
    generar_individuo_recursive(individuo_ref, participantes_disponibles, asientos_restantes - 1)
  return

def generar_poblacion_inicial(participantes: list[Participante], asientos: int, poblacion_inicial_size: int):
  poblacion_inicial:list[Individuo] = []
  ids = [p.id for p in participantes]
  for i in range(poblacion_inicial_size):
    individuo = Individuo(
      nombre=f"gen1-index{i}",
      posiciones=["" for _ in range(asientos)],
      generacion=1,
      aptitud=None
    )
    generar_individuo_recursive(individuo, list(ids), asientos - 1)
    poblacion_inicial.append(individuo)
  return poblacion_inicial

def handle_repetidos(ids_total: set[str], individuo_ref: Individuo):
  ids_abs_individuo = set(individuo_ref.posiciones)
  ids_disponibles = ids_total - ids_abs_individuo
  posiciones_por_valor = defaultdict(list)
  for i, value in enumerate(individuo_ref.posiciones):
    posiciones_por_valor[value].append(i)
  repetidos:dict[str, list[int]] = { val: indices for val, indices in posiciones_por_valor.items() if len(indices) > 1 }
  for repetidos_round in repetidos.values():
    while len(repetidos_round) > 1:
      posicion_a_cambiar = distribucion_uniforme(repetidos_round)
      id_a_utilizar = distribucion_uniforme(list(ids_total))
      individuo_ref.posiciones[posicion_a_cambiar] = id_a_utilizar
      ids_disponibles.remove(id_a_utilizar)
      repetidos_round.remove(posicion_a_cambiar)

def handle_cruza(padre: Individuo, madre: Individuo, num_generacion: int, ids:list[str]):
  hijo1 = Individuo(
    nombre=f"hijo1-gen{num_generacion} -> ({padre.nombre} <||> {madre.nombre})",
    posiciones=["" for _ in range(len(padre.posiciones))],
    generacion=num_generacion
    )
  hijo2 = Individuo(
    nombre=f"hijo2-gen{num_generacion} -> ({madre.nombre} <||> {padre.nombre})",
    posiciones=["" for _ in range(len(madre.posiciones))],
    generacion=num_generacion
  )
  turno = CruzaGenTurno.PADRE
  for i in range(hijo1.posiciones):
    if turno == CruzaGenTurno.PADRE:
      hijo1.posiciones[i] = padre.posiciones[i]
      turno = CruzaGenTurno.MADRE
    if turno == CruzaGenTurno.MADRE:
      hijo1.posiciones[i] = madre.posiciones[i]
      turno = CruzaGenTurno.PADRE
  handle_repetidos(set(ids), hijo1)
  
  turno = CruzaGenTurno.MADRE
  for i in range(hijo2.posiciones):
    if turno == CruzaGenTurno.PADRE:
      hijo2.posiciones[i] = padre.posiciones[i]
      turno = CruzaGenTurno.MADRE
    if turno == CruzaGenTurno.MADRE:
      hijo2.posiciones[i] = madre.posiciones[i]
      turno = CruzaGenTurno.PADRE
  handle_repetidos(set(ids), hijo2)
  
  return hijo1, hijo2

def handle_mutacion_por_cambio_de_id(individuo_ref: Individuo, ids_disponibles: set[str]):
  posicion_a_cambiar = individuo_ref.posiciones.index(distribucion_uniforme(individuo_ref.posiciones))
  id_a_utilizar = distribucion_uniforme(list(ids_disponibles))
  id_reemplazada = individuo_ref.posiciones[posicion_a_cambiar]
  individuo_ref.posiciones[posicion_a_cambiar] = id_a_utilizar
  ids_disponibles.remove(id_a_utilizar)
  ids_disponibles.add(id_reemplazada)

def handle_mutacion_por_cambio_de_posiciones(individuo_ref: Individuo):
  pass

def handle_mutacion(individuo_ref: Individuo, ids_disponibles: set[str]):
  posiciones_disponibles = set(individuo_ref.posiciones) - ids_disponibles
  tipo_mutacion = distribucion_uniforme_ponderada([
    (TipoMutacion.CAMBIO_DE_ID, 0.8),
    (TipoMutacion.CAMBIO_DE_POSICIONES, 0.2)
  ])
  pass
  

def handle_generacion(resultados_ref: Resultado, num_generacion: int):
  pass

def run_ag(data: RunAgEventBody, out: OutFunc):
  participantes = parse_participantes(data)
  resolve_missing(data)
  
  resultados = Resultado(None, None, None, [])
  
  poblacion_inicial = generar_poblacion_inicial(participantes, data["num_asientos"], data["poblacion_inicial_size"])


app = FastAPI()
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
  await ws.accept()
  try:
    while True:
      data = ws.receive_text()
      parsed_text = json.loads(data)
      event_name = parsed_text["event_name"]
      event_data = parsed_text["event_data"]
  except WebSocketDisconnect as error:
    print(f"cliente desconectado.\n{error}")