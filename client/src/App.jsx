import React, { useState, useEffect, useRef } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts';
import { Play, Pause, RotateCcw, Plus, Trash2, Zap, Users, Activity } from 'lucide-react';

// --- Constantes y Utilidades ---
const WS_URL = "ws://localhost:8000/ws";

const PLANTILLA_PARTICIPANTES = [
  { id: "p1", nombre: "Ana", peso_kg: 55 },
  { id: "p2", nombre: "Beto", peso_kg: 80 },
  { id: "p3", nombre: "Carla", peso_kg: 62 },
  { id: "p4", nombre: "Daniel", peso_kg: 95 },
  { id: "p5", nombre: "Elena", peso_kg: 50 },
  { id: "p6", nombre: "Fabian", peso_kg: 75 },
  { id: "p7", nombre: "Gaby", peso_kg: 60 },
  { id: "p8", nombre: "Hugo", peso_kg: 88 },
];

const CONFIG_INICIAL = {
  poblacion_maxima: 50,
  poblacion_inicial_size: 30,
  num_asientos: 5,
  num_generaciones: 100,
  umbral_cruza: 0.8,
  umbral_mutacion: 0.1,
  prob_mutacion_cambio_id: 0.8,
  prob_mutacion_cambio_pos: 0.2
};

// --- Componente: Balanza Visual ---
const BalanzaVisual = ({ torque, maxTorque }) => {
  // Calculamos rotación. Clampeamos entre -30 y 30 grados para que sea visualmente agradable
  // Un torque de 0 es 0 grados.
  const rangoVisual = 30; // grados maximos
  const factor = maxTorque > 0 ? maxTorque : 100; 
  // Invertimos el signo si es necesario según tu lógica (Positivo derecha, Negativo izquierda)
  const rotacion = Math.max(-rangoVisual, Math.min(rangoVisual, (torque / factor) * rangoVisual));

  return (
    <div className="flex flex-col items-center justify-center p-4 bg-slate-50 rounded-lg border border-slate-200 h-64">
      <h3 className="text-sm font-bold text-slate-500 mb-4">Visualización de Torque (Balanza)</h3>
      <div className="relative w-64 h-32 flex items-end justify-center">
        {/* Base de la balanza */}
        <div className="absolute bottom-0 w-0 h-0 border-l-[20px] border-l-transparent border-r-[20px] border-r-transparent border-b-[40px] border-b-slate-700"></div>
        
        {/* Brazo de la balanza (Animado) */}
        <div 
          className="absolute bottom-[35px] w-64 h-2 bg-slate-800 rounded transition-transform duration-300 ease-out flex items-center justify-between px-2"
          style={{ transform: `rotate(${rotacion}deg)`, transformOrigin: "center" }}
        >
          {/* Platillo Izquierdo */}
          <div className="w-8 h-8 bg-blue-500 rounded-full shadow-md transform -translate-y-4"></div>
           {/* Centro Eje */}
           <div className="w-4 h-4 bg-white rounded-full border-2 border-slate-800 z-10"></div>
          {/* Platillo Derecho */}
          <div className="w-8 h-8 bg-red-500 rounded-full shadow-md transform -translate-y-4"></div>
          
          {/* Linea de referencia del individuo (Visual) */}
          <div className="absolute w-full h-[1px] bg-red-400 opacity-50 top-1/2 left-0" />
        </div>

        {/* Linea de Referencia Estática (Horizonte) */}
        <div className="absolute bottom-[39px] w-72 h-[1px] bg-green-500 border-t border-dashed border-green-600 z-0 pointer-events-none"></div>
      </div>
      <div className="mt-6 text-center">
        <span className={`text-xl font-mono font-bold ${torque === 0 ? 'text-green-600' : 'text-slate-700'}`}>
          Torque: {torque.toFixed(2)}
        </span>
        <p className="text-xs text-slate-400">
          {torque < 0 ? "Inclinación: Izquierda" : torque > 0 ? "Inclinación: Derecha" : "Balanceado"}
        </p>
      </div>
    </div>
  );
};

// --- Componente Principal ---
export default function GeneticAlgorithmApp() {
  // Estados de entrada
  const [participantes, setParticipantes] = useState([]);
  const [nuevoNombre, setNuevoNombre] = useState("");
  const [nuevoPeso, setNuevoPeso] = useState("");
  const [config, setConfig] = useState(CONFIG_INICIAL);

  // Estados de Websocket y Ejecución
  const [ws, setWs] = useState(null);
  const [status, setStatus] = useState("Desconectado");
  const [resultado, setResultado] = useState(null);
  const [loading, setLoading] = useState(false);

  // Estados de Reproducción (Video)
  const [frameActual, setFrameActual] = useState(0);
  const [jugando, setJugando] = useState(false);
  const timerRef = useRef(null);

  // --- Lógica WebSocket ---
  useEffect(() => {
    const socket = new WebSocket(WS_URL);
    socket.onopen = () => setStatus("Conectado");
    socket.onclose = () => setStatus("Desconectado");
    socket.onmessage = (event) => {
      const response = JSON.parse(event.data);
      if (response.event_name === "ag_completed") {
        procesarResultados(response.data);
      }
    };
    setWs(socket);
    return () => socket.close();
  }, []);

  const procesarResultados = (data) => {
    setLoading(false);
    // Transformamos los datos para la gráfica (Valor Absoluto)
    const generacionesProcesadas = data.generaciones.map(gen => ({
      ...gen,
      abs_mejor: Math.abs(gen.mejor_individuo.aptitud),
      abs_peor: Math.abs(gen.peor_individuo.aptitud),
      abs_promedio: Math.abs(gen.aptitud_promedio),
      raw_mejor: gen.mejor_individuo.aptitud // Guardamos el original para la balanza
    }));
    
    setResultado({ ...data, generaciones: generacionesProcesadas });
    setFrameActual(0); // Resetear video al inicio
  };

  const ejecutarAlgoritmo = () => {
    if (!ws || participantes.length < config.num_asientos) {
      alert("Faltan participantes o conexión.");
      return;
    }
    setLoading(true);
    setResultado(null);
    const payload = {
      event_name: "run_ag",
      event_data: {
        ...config,
        participantes
      }
    };
    ws.send(JSON.stringify(payload));
  };

  // --- Gestión de Participantes ---
  const agregarParticipante = () => {
    if (!nuevoNombre || !nuevoPeso) return;
    const nuevo = {
      id: crypto.randomUUID().slice(0, 8),
      nombre: nuevoNombre,
      peso_kg: parseFloat(nuevoPeso)
    };
    setParticipantes([...participantes, nuevo]);
    setNuevoNombre("");
    setNuevoPeso("");
  };

  const cargarPlantilla = () => setParticipantes([...PLANTILLA_PARTICIPANTES]);

  // --- Lógica del "Video" ---
  useEffect(() => {
    if (jugando && resultado) {
      timerRef.current = setInterval(() => {
        setFrameActual(prev => {
          if (prev >= resultado.generaciones.length - 1) {
            setJugando(false);
            return prev;
          }
          return prev + 1;
        });
      }, 100); // Velocidad: 100ms por generación
    } else {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [jugando, resultado]);

  // Datos para renderizar el frame actual
  const datosFrameActual = resultado ? resultado.generaciones[frameActual] : null;
  const maxTorqueHistorico = resultado 
    ? Math.max(...resultado.generaciones.map(g => Math.abs(g.peor_individuo.aptitud)))
    : 100;

  // Datos acumulados para la gráfica (efecto de trazado en tiempo real)
  const datosGraficaAnimada = resultado 
    ? resultado.generaciones.slice(0, frameActual + 1) 
    : [];

  return (
    <div className="min-h-screen bg-gray-100 p-8 font-sans text-gray-800">
      <header className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-blue-700">Optimización de Torque (AG)</h1>
          <p className="text-sm text-gray-500">Algoritmo Genético para balanceo de cargas</p>
        </div>
        <div className={`px-4 py-2 rounded-full text-sm font-bold ${status === "Conectado" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
          WS: {status}
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* --- COLUMNA IZQUIERDA: Configuración --- */}
        <div className="lg:col-span-1 space-y-6">
          
          {/* Panel Participantes */}
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold flex items-center gap-2"><Users size={18}/> Participantes</h2>
              <button onClick={cargarPlantilla} className="text-xs text-blue-600 hover:underline">Cargar Plantilla</button>
            </div>
            
            <div className="flex gap-2 mb-4">
              <input 
                className="w-1/2 p-2 border rounded text-sm" 
                placeholder="Nombre" 
                value={nuevoNombre}
                onChange={e => setNuevoNombre(e.target.value)}
              />
              <input 
                className="w-1/4 p-2 border rounded text-sm" 
                placeholder="Kg" 
                type="number"
                value={nuevoPeso}
                onChange={e => setNuevoPeso(e.target.value)}
              />
              <button onClick={agregarParticipante} className="w-1/4 bg-blue-600 text-white rounded hover:bg-blue-700 flex justify-center items-center">
                <Plus size={16}/>
              </button>
            </div>

            <div className="h-48 overflow-y-auto border rounded divide-y">
              {participantes.map(p => (
                <div key={p.id} className="p-2 text-sm flex justify-between items-center bg-gray-50">
                  <span>{p.nombre} ({p.peso_kg}kg)</span>
                  <button onClick={() => setParticipantes(participantes.filter(x => x.id !== p.id))} className="text-red-400 hover:text-red-600">
                    <Trash2 size={14}/>
                  </button>
                </div>
              ))}
              {participantes.length === 0 && <p className="text-center text-gray-400 py-4 text-xs">Sin participantes</p>}
            </div>
          </div>

          {/* Panel Configuración AG */}
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
             <h2 className="text-lg font-semibold mb-4 flex items-center gap-2"><Zap size={18}/> Parámetros AG</h2>
             <div className="grid grid-cols-2 gap-4 text-sm">
                <label>Generaciones: <input type="number" className="w-full border p-1 rounded" value={config.num_generaciones} onChange={(e) => setConfig({...config, num_generaciones: parseInt(e.target.value)})}/></label>
                <label>Población Max: <input type="number" className="w-full border p-1 rounded" value={config.poblacion_maxima} onChange={(e) => setConfig({...config, poblacion_maxima: parseInt(e.target.value)})}/></label>
                <label>Asientos: <input type="number" className="w-full border p-1 rounded" value={config.num_asientos} onChange={(e) => setConfig({...config, num_asientos: parseInt(e.target.value)})}/></label>
                <label>Mutación Rate: <input type="number" step="0.01" className="w-full border p-1 rounded" value={config.umbral_mutacion} onChange={(e) => setConfig({...config, umbral_mutacion: parseFloat(e.target.value)})}/></label>
             </div>
             <button 
              onClick={ejecutarAlgoritmo}
              disabled={loading || status !== "Conectado"}
              className="mt-6 w-full bg-indigo-600 text-white py-3 rounded-lg font-bold shadow hover:bg-indigo-700 disabled:bg-gray-400 transition-colors"
             >
               {loading ? "Evolucionando..." : "Ejecutar Algoritmo"}
             </button>
          </div>
        </div>

        {/* --- COLUMNA DERECHA: Resultados --- */}
        <div className="lg:col-span-2 space-y-6">
          {resultado && (
            <>
              {/* Sección de Video / Reproducción */}
              <div className="bg-white p-6 rounded-xl shadow-md border border-indigo-100">
                <div className="flex justify-between items-end mb-4">
                  <div>
                    <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                      <Activity className="text-indigo-500"/> Evolución en Tiempo Real
                    </h2>
                    <p className="text-sm text-slate-500">Generación Actual: <span className="font-mono text-indigo-600 text-lg">{datosFrameActual?.numero}</span> / {config.num_generaciones}</p>
                  </div>
                  
                  {/* Controles del Video */}
                  <div className="flex gap-2">
                    <button onClick={() => setFrameActual(0)} className="p-2 rounded hover:bg-gray-100"><RotateCcw size={20}/></button>
                    <button 
                      onClick={() => setJugando(!jugando)} 
                      className={`flex items-center gap-2 px-4 py-2 rounded-lg text-white font-bold ${jugando ? 'bg-amber-500 hover:bg-amber-600' : 'bg-green-600 hover:bg-green-700'}`}
                    >
                      {jugando ? <><Pause size={18}/> Pausa</> : <><Play size={18}/> Reproducir</>}
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Gráfica Animada */}
                  <div className="h-64 bg-slate-50 rounded border border-slate-100 p-2">
                    <p className="text-xs text-center text-slate-400 mb-2">Convergencia de Aptitud (Absoluta)</p>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={datosGraficaAnimada}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                        <XAxis dataKey="numero" hide />
                        <YAxis domain={[0, 'auto']} />
                        <Tooltip labelFormatter={(label) => `Gen: ${label}`} />
                        <Legend />
                        <Line type="monotone" dataKey="abs_mejor" stroke="#10b981" strokeWidth={2} dot={false} name="Mejor (→0)" isAnimationActive={false} />
                        <Line type="monotone" dataKey="abs_promedio" stroke="#3b82f6" strokeWidth={2} dot={false} name="Promedio" isAnimationActive={false} />
                        <Line type="monotone" dataKey="abs_peor" stroke="#ef4444" strokeWidth={1} strokeDasharray="3 3" dot={false} name="Peor" isAnimationActive={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Balanza Animada */}
                  <BalanzaVisual 
                    torque={datosFrameActual?.raw_mejor || 0} 
                    maxTorque={maxTorqueHistorico} 
                  />
                </div>
                
                {/* Slider de Progreso */}
                <input 
                  type="range" 
                  min="0" 
                  max={resultado.generaciones.length - 1} 
                  value={frameActual} 
                  onChange={(e) => {
                    setJugando(false);
                    setFrameActual(parseInt(e.target.value));
                  }}
                  className="w-full mt-6 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
                />
              </div>

              {/* Estadísticas Globales */}
              <div className="grid grid-cols-3 gap-4">
                <CardStat label="Mejor Aptitud Final" value={resultado.mejor_global?.aptitud.toFixed(4)} color="text-green-600" />
                <CardStat label="Peor Aptitud Final" value={resultado.generaciones[resultado.generaciones.length-1].peor_individuo.aptitud.toFixed(4)} color="text-red-500" />
                <CardStat label="Promedio Final" value={resultado.generaciones[resultado.generaciones.length-1].aptitud_promedio.toFixed(4)} color="text-blue-500" />
              </div>

              {/* Tabla de Datos */}
              <div className="bg-white rounded-xl shadow overflow-hidden border border-gray-200">
                <div className="bg-gray-50 px-6 py-4 border-b">
                  <h3 className="font-semibold text-gray-700">Registro Detallado por Generación</h3>
                </div>
                <div className="max-h-64 overflow-y-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-gray-100 text-gray-600 sticky top-0">
                      <tr>
                        <th className="px-6 py-3">Gen #</th>
                        <th className="px-6 py-3">Mejor Individuo (IDs Posiciones)</th>
                        <th className="px-6 py-3 text-right">Aptitud (Torque)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {resultado.generaciones.map((gen) => (
                        <tr key={gen.numero} className="hover:bg-gray-50">
                          <td className="px-6 py-2 font-mono text-gray-500">{gen.numero}</td>
                          <td className="px-6 py-2">
                            <div className="flex gap-1">
                              {gen.mejor_individuo.posiciones.map((pos, i) => (
                                <span key={i} className="bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded text-xs border border-indigo-100">
                                  {pos}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className={`px-6 py-2 text-right font-mono font-bold ${Math.abs(gen.mejor_individuo.aptitud) < 0.1 ? 'text-green-600' : 'text-gray-700'}`}>
                            {gen.mejor_individuo.aptitud.toFixed(4)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}

          {!resultado && !loading && (
            <div className="h-64 flex flex-col items-center justify-center bg-gray-50 rounded-xl border-2 border-dashed border-gray-300 text-gray-400">
              <Activity size={48} className="mb-2 opacity-20"/>
              <p>Configura los parámetros y ejecuta el algoritmo para ver los resultados.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// --- Componente auxiliar pequeño ---
const CardStat = ({ label, value, color }) => (
  <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-100 text-center">
    <p className="text-xs text-gray-500 uppercase font-semibold">{label}</p>
    <p className={`text-2xl font-bold ${color}`}>{value}</p>
  </div>
);