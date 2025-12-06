import React, { useState } from 'react';
import { useFPL } from '../context/FPLContext';
import { fplService } from '../services/api';
import { Zap, Save, RefreshCw } from 'lucide-react';

const SimulationMode = () => {
    const { teamData, fplService } = useFPL();
    const [simulating, setSimulating] = useState(false);
    const [result, setResult] = useState(null);

    // Mock initial selection (top players) for simulation if teamData is missing
    const initialSelection = teamData?.players?.slice(0, 15) || [];

    const handleSimulate = async () => {
        setSimulating(true);
        try {
            // Use current team or drafted players
            const teamIds = initialSelection.map(p => p.id);
            const response = await fplService.simulateTeam({
                team_ids: teamIds,
                bank: 100.0 // Mock bank for now, or fetch
            });

            const data = response.data;
            setResult({
                projected_points: data.stats.total_pred_points.toFixed(1),
                captain: data.captain?.web_name || 'Unknown',
                vice: data.vice_captain?.web_name || 'Unknown',
                optimal_xi: data.starting_xi,
                bench: data.bench
            });
        } catch (err) {
            console.error("Simulation failed:", err);
            // Optionally set error state here
        } finally {
            setSimulating(false);
        }
    };

    return (
        <div className="space-y-6">
            <header className="mb-6 flex justify-between items-end">
                <div>
                    <h2 className="text-2xl font-bold text-white">Simulation Mode</h2>
                    <p className="text-gray-400">Test different lineups and transfer combinations.</p>
                </div>
                <button
                    onClick={handleSimulate}
                    disabled={simulating}
                    className={`flex items-center gap-2 px-6 py-2 rounded-lg font-bold text-white shadow-lg transition-all ${simulating ? 'bg-gray-600 cursor-not-allowed' : 'bg-gradient-to-r from-yellow-500 to-orange-600 hover:from-yellow-400 hover:to-orange-500'
                        }`}
                >
                    {simulating ? <RefreshCw className="animate-spin" /> : <Zap />}
                    {simulating ? 'Simulating...' : 'Run Simulation'}
                </button>
            </header>

            {/* Main Workspace */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Left: Input / Squad Selection */}
                <div className="lg:col-span-2 bg-gray-900 rounded-xl p-6 border border-gray-800">
                    <h3 className="text-lg font-semibold text-white mb-4">Draft Squad</h3>
                    <div className="min-h-[400px] flex items-center justify-center border-2 border-dashed border-gray-700 rounded-xl bg-gray-800/30">
                        {initialSelection.length > 0 ? (
                            <div className="grid grid-cols-5 gap-2 w-full p-4">
                                {initialSelection.map(p => (
                                    <div key={p.id} className="bg-gray-800 p-2 rounded text-center border border-gray-700">
                                        <div className="text-xs font-bold text-white truncate">{p.web_name}</div>
                                        <div className="text-[10px] text-gray-500">{p.now_cost / 10}m</div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-gray-500">Load a team to populate players</p>
                        )}
                    </div>
                </div>

                {/* Right: Results / Config */}
                <div className="space-y-6">
                    {/* Config Panel */}
                    <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
                        <h3 className="text-white font-bold mb-4 flex items-center gap-2">
                            <Save size={18} /> Configuration
                        </h3>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-xs text-gray-400 mb-1">Bank Budget (£m)</label>
                                <input type="number" className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-white" defaultValue="0.5" />
                            </div>
                            <div>
                                <label className="block text-xs text-gray-400 mb-1">Free Transfers</label>
                                <select className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-white">
                                    <option>1</option>
                                    <option>2</option>
                                    <option>Unlimited (Wildcard)</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    {/* Results Panel (Conditional) */}
                    {result && (
                        <div className="bg-gradient-to-b from-purple-900/50 to-gray-900 rounded-xl p-6 border border-purple-500/30 animate-in fade-in slide-in-from-bottom-4">
                            <h3 className="text-xl font-bold text-white mb-4">Projected Result</h3>
                            <div className="flex justify-between items-center mb-4">
                                <span className="text-gray-300">Total Points</span>
                                <span className="text-2xl font-bold text-green-400">{result.projected_points}</span>
                            </div>
                            <div className="space-y-2 text-sm">
                                <div className="flex justify-between">
                                    <span className="text-gray-400">Captain</span>
                                    <span className="text-white font-medium">{result.captain}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-gray-400">Vice</span>
                                    <span className="text-white font-medium">{result.vice}</span>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default SimulationMode;
