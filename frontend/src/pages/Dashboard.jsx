import React, { useEffect, useState } from 'react';
import { useFPL } from '../context/FPLContext';
import { Trophy, Users, TrendingUp, AlertCircle, Loader } from 'lucide-react';

const Dashboard = () => {
    const { teamId, saveTeamId, teamData, fetchTeamAnalysis, loading, error } = useFPL();
    const [inputId, setInputId] = useState('');

    useEffect(() => {
        if (teamId && !teamData) {
            fetchTeamAnalysis(teamId);
        }
    }, [teamId]);

    const handleSearch = (e) => {
        e.preventDefault();
        if (inputId) {
            saveTeamId(inputId);
            fetchTeamAnalysis(inputId);
        }
    };

    if (!teamId) {
        return (
            <div className="flex flex-col items-center justify-center h-[60vh] text-center">
                <Trophy size={64} className="text-purple-500 mb-4" />
                <h2 className="text-3xl font-bold text-white mb-2">Welcome to FPL WIZ</h2>
                <p className="text-gray-400 mb-6 max-w-md">Enter your FPL Team ID to start analyzing your squad with AI-powered insights.</p>
                <form onSubmit={handleSearch} className="flex gap-2">
                    <input
                        type="number"
                        placeholder="Team ID (e.g. 123456)"
                        className="bg-gray-800 border border-gray-700 text-white px-4 py-2 rounded-lg focus:outline-none focus:border-purple-500"
                        value={inputId}
                        onChange={(e) => setInputId(e.target.value)}
                    />
                    <button type="submit" className="bg-purple-600 hover:bg-purple-500 text-white px-6 py-2 rounded-lg font-medium transition-colors">
                        Start
                    </button>
                </form>
                <p className="text-xs text-gray-600 mt-4">Don't know your ID? Check the URL when viewing your points on the FPL site.</p>
            </div>
        );
    }

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-[60vh]">
                <Loader className="animate-spin text-purple-500 mb-4" size={48} />
                <p className="text-gray-400">Analyzing your team...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex flex-col items-center justify-center h-[60vh]">
                <AlertCircle className="text-red-500 mb-4" size={48} />
                <h2 className="text-xl font-bold text-white mb-2">Error Loading Data</h2>
                <p className="text-gray-400 mb-4">{error}</p>
                <button onClick={() => fetchTeamAnalysis(teamId)} className="bg-gray-800 hover:bg-gray-700 text-white px-4 py-2 rounded-lg">
                    Try Again
                </button>
            </div>
        );
    }

    // Extract Data safely
    const info = teamData?.team_info || {};
    const players = teamData?.players || [];
    const gw = teamData?.gameweek?.current || '-';

    // Calculate aggregate stats
    const totalValue = (players.reduce((acc, p) => acc + p.now_cost, 0) / 10).toFixed(1);
    const bestPlayer = players.reduce((prev, current) => (prev.pred_points > current.pred_points) ? prev : current, { web_name: '-', pred_points: 0 });

    return (
        <div className="space-y-6">
            <header className="mb-8 flex justify-between items-end">
                <div>
                    <h2 className="text-3xl font-bold text-white">{info.name || 'My Team'}</h2>
                    <p className="text-gray-400">Manager: {info.player_first_name} {info.player_last_name} • GW {gw}</p>
                </div>
                <button onClick={() => { saveTeamId(''); setInputId(''); }} className="text-xs text-gray-500 hover:text-white underline">
                    Change Team
                </button>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {/* Metric Cards */}
                <div className="p-6 rounded-2xl bg-gray-800/50 border border-gray-700/50 backdrop-blur-sm">
                    <div className="flex items-center justify-between mb-2">
                        <h3 className="text-sm font-medium text-gray-400">Overall Rank</h3>
                        <Trophy size={16} className="text-yellow-500" />
                    </div>
                    <p className="text-3xl font-bold text-white">{info.summary_overall_rank?.toLocaleString() || '-'}</p>
                    <span className="text-xs text-gray-500 font-medium">Points: {info.summary_overall_points}</span>
                </div>

                <div className="p-6 rounded-2xl bg-gray-800/50 border border-gray-700/50 backdrop-blur-sm">
                    <div className="flex items-center justify-between mb-2">
                        <h3 className="text-sm font-medium text-gray-400">Squad Value</h3>
                        <Users size={16} className="text-purple-500" />
                    </div>
                    <p className="text-3xl font-bold text-white">£{totalValue}m</p>
                    <span className="text-xs text-gray-500 font-medium">Bank: £{(info.summary_event_points / 10).toFixed(1)}m (Check API)</span>
                </div>

                <div className="p-6 rounded-2xl bg-gray-800/50 border border-gray-700/50 backdrop-blur-sm">
                    <div className="flex items-center justify-between mb-2">
                        <h3 className="text-sm font-medium text-gray-400">GW Points</h3>
                        <TrendingUp size={16} className="text-green-500" />
                    </div>
                    <p className="text-3xl font-bold text-white">{info.summary_event_points || 0}</p>
                    <span className="text-xs text-green-400 font-medium">Rank: {info.summary_event_rank?.toLocaleString()}</span>
                </div>

                <div className="p-6 rounded-2xl bg-gray-800/50 border border-gray-700/50 backdrop-blur-sm border-l-4 border-l-purple-500">
                    <div className="flex items-center justify-between mb-2">
                        <h3 className="text-sm font-medium text-gray-400">Model Top Pick</h3>
                        <div className="text-xs bg-purple-500 text-white px-2 py-0.5 rounded-full">AI</div>
                    </div>
                    <p className="text-xl font-bold text-white truncate">{bestPlayer.web_name}</p>
                    <p className="text-xs text-purple-300 font-medium">xB: {bestPlayer.pred_points?.toFixed(1)} pts</p>
                </div>
            </div>

            {/* Tables & Layouts */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 p-6 rounded-2xl bg-gray-900 border border-gray-800 min-h-[300px]">
                    <h3 className="text-lg font-semibold text-white mb-4">Starting XI (Projected)</h3>
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm text-gray-400">
                            <thead className="text-xs uppercase bg-gray-800/50 text-gray-300">
                                <tr>
                                    <th className="px-4 py-3 rounded-l-lg">Player</th>
                                    <th className="px-4 py-3">Pos</th>
                                    <th className="px-4 py-3">Fix</th>
                                    <th className="px-4 py-3">Form</th>
                                    <th className="px-4 py-3 rounded-r-lg text-right">xPts</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-800">
                                {players.slice(0, 11).map((p) => (
                                    <tr key={p.id} className="hover:bg-gray-800/30 transition-colors">
                                        <td className="px-4 py-3 font-medium text-white">{p.web_name}</td>
                                        <td className="px-4 py-3">{p.element_type_name || p.element_type}</td>
                                        <td className="px-4 py-3 text-xs">{p.opponent_str || '-'}</td>
                                        <td className="px-4 py-3 text-white">{p.weighted_form ? parseFloat(p.weighted_form).toFixed(1) : '-'}</td>
                                        <td className="px-4 py-3 text-right font-bold text-purple-400">{p.pred_points?.toFixed(1)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
                <div className="p-6 rounded-2xl bg-gray-900 border border-gray-800 min-h-[300px]">
                    <h3 className="text-lg font-semibold text-white mb-4">Transfer Watchlist</h3>
                    <div className="space-y-4">
                        {/* Mock Data for now, can be replaced with real transfer suggestions */}
                        <div className="flex items-center justify-between p-3 rounded-lg bg-gray-800/30 border border-gray-700/30">
                            <div className="flex items-center space-x-3">
                                <div className="w-10 h-10 rounded-full bg-gray-700 flex items-center justify-center text-xs">M.Salah</div>
                                <div>
                                    <p className="text-sm font-bold text-white">Salah</p>
                                    <p className="text-xs text-gray-500">LIV • £13.2m</p>
                                </div>
                            </div>
                            <div className="text-right">
                                <p className="text-sm font-bold text-green-400">8.4</p>
                                <p className="text-[10px] text-gray-500">xPts</p>
                            </div>
                        </div>
                        <div className="flex items-center justify-between p-3 rounded-lg bg-gray-800/30 border border-gray-700/30">
                            <div className="flex items-center space-x-3">
                                <div className="w-10 h-10 rounded-full bg-gray-700 flex items-center justify-center text-xs">Saka</div>
                                <div>
                                    <p className="text-sm font-bold text-white">Saka</p>
                                    <p className="text-xs text-gray-500">ARS • £10.1m</p>
                                </div>
                            </div>
                            <div className="text-right">
                                <p className="text-sm font-bold text-green-400">7.2</p>
                                <p className="text-[10px] text-gray-500">xPts</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Dashboard;
