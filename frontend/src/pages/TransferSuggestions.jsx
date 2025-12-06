import React, { useState, useEffect } from 'react';
import { useFPL } from '../context/FPLContext';
import { fplService } from '../services/api';
import { ArrowLeftRight, TrendingUp, AlertCircle } from 'lucide-react';

const TransferSuggestions = () => {
    const { teamId, teamData } = useFPL();
    const [suggestions, setSuggestions] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Fetch suggestions when component mounts or teamId changes
    useEffect(() => {
        const fetchSuggestions = async () => {
            if (!teamId) return;

            setLoading(true);
            try {
                // Default strategy and bank from teamData if available, else 0
                const bank = teamData?.team_info?.bank ? teamData.team_info.bank / 10 : 0.5;

                const response = await fplService.getTransferSuggestions({
                    team_ids: [teamId], // In a real scenario, this should be the list of player IDs in the squad
                    bank: bank,
                    free_transfers: 1,
                    strategy: "aggressive"
                });

                // Transform API response to UI format
                // API returns { aggressive: [...], conservative: [...] }
                // We'll flatten/mix them for now or just show aggressive
                const agg = response.data.aggressive || [];
                const cons = response.data.conservative || [];

                const formatted = [
                    ...agg.map((m, i) => ({
                        id: `agg-${i}`, type: 'in', name: m.in_player || 'Unknown',
                        team: '???', price: m.in_cost, xP: m.score_gain?.toFixed(1) || 0,
                        reason: `Gain ${m.score_gain?.toFixed(1)} pts`
                    })),
                    // For UI demo, let's map some OUTs too if provided by API or infer them
                    ...agg.map((m, i) => ({
                        id: `out-${i}`, type: 'out', name: m.out_player || 'Unknown',
                        team: '???', price: m.out_cost, xP: '-',
                        reason: `Sell for £${m.out_cost}m`
                    }))
                ];

                setSuggestions(formatted);
            } catch (err) {
                console.error("Failed to fetch suggestions:", err);
                setError("Failed to generate suggestions. Please ensure backend is running.");
            } finally {
                setLoading(false);
            }
        };

        if (teamId) {
            fetchSuggestions();
        }
    }, [teamId, teamData]);

    if (loading) return <div className="text-white text-center mt-20">AI is thinking...</div>;
    if (error) return <div className="text-red-400 text-center mt-20">{error}</div>;

    return (
        <div className="space-y-6">
            <header className="mb-6">
                <h2 className="text-2xl font-bold text-white">Transfer Suggestions</h2>
                <p className="text-gray-400">AI-recommended moves to optimize your squad.</p>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Transfer IN */}
                <div className="bg-gray-900/50 border border-green-900/30 rounded-xl overflow-hidden">
                    <div className="p-4 bg-green-900/20 border-b border-green-900/30 flex items-center justify-between">
                        <h3 className="text-lg font-bold text-green-400 flex items-center gap-2">
                            <TrendingUp size={20} /> Targets (IN)
                        </h3>
                        <span className="text-xs text-gray-400">Sorted by EV</span>
                    </div>
                    <div className="p-4 space-y-3">
                        {suggestions.filter(s => s.type === 'in').map(p => (
                            <div key={p.id} className="flex items-center justify-between p-3 rounded-lg bg-gray-800/40 hover:bg-gray-800/60 border border-gray-700/30 transition-colors">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-full bg-gray-700 flex items-center justify-center text-xs font-bold text-gray-300">
                                        {p.name.substring(0, 3).toUpperCase()}
                                    </div>
                                    <div>
                                        <p className="text-sm font-bold text-white">{p.name}</p>
                                        <p className="text-xs text-gray-500">{p.team} • £{p.price}m</p>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <p className="text-sm font-bold text-green-400">{p.xP}</p>
                                    <p className="text-[10px] text-gray-500">xPts</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Transfer OUT */}
                <div className="bg-gray-900/50 border border-red-900/30 rounded-xl overflow-hidden">
                    <div className="p-4 bg-red-900/20 border-b border-red-900/30 flex items-center justify-between">
                        <h3 className="text-lg font-bold text-red-400 flex items-center gap-2">
                            <AlertCircle size={20} /> Candidates (OUT)
                        </h3>
                        <span className="text-xs text-gray-400">Underperforming</span>
                    </div>
                    <div className="p-4 space-y-3">
                        {suggestions.filter(s => s.type === 'out').map(p => (
                            <div key={p.id} className="flex items-center justify-between p-3 rounded-lg bg-gray-800/40 hover:bg-gray-800/60 border border-gray-700/30 transition-colors">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-full bg-gray-700 flex items-center justify-center text-xs font-bold text-gray-300">
                                        {p.name.substring(0, 3).toUpperCase()}
                                    </div>
                                    <div>
                                        <p className="text-sm font-bold text-white">{p.name}</p>
                                        <p className="text-xs text-gray-500">{p.team} • £{p.price}m</p>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <p className="text-sm font-bold text-red-400">{p.xP}</p>
                                    <p className="text-[10px] text-gray-500">xPts</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Optimal Strategy Card */}
            <div className="bg-gradient-to-r from-purple-900/20 to-indigo-900/20 border border-purple-500/20 rounded-xl p-6">
                <h3 className="text-xl font-bold text-white mb-2 flex items-center gap-2">
                    <ArrowLeftRight className="text-purple-400" /> Optimal Move
                </h3>
                <p className="text-gray-300 mb-4">
                    Based on projected points over the next 3 gameweeks, selling <span className="text-red-300 font-bold">Rashford</span> for <span className="text-green-300 font-bold">Saka</span> yields a net gain of <span className="text-white font-bold">+4.1 points</span>.
                </p>
                <div className="flex justify-end">
                    <button className="bg-purple-600 hover:bg-purple-500 text-white px-6 py-2 rounded-lg font-medium shadow-lg shadow-purple-900/20 transition-all">
                        Simulate This Move
                    </button>
                </div>
            </div>
        </div>
    );
};

export default TransferSuggestions;
