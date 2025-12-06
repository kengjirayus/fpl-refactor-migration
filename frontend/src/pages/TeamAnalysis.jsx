import React, { useEffect, useState } from 'react';
import { useFPL } from '../context/FPLContext';
import PitchView from '../components/PitchView';
import { Loader, AlertCircle, RefreshCw, Trophy } from 'lucide-react';

const TeamAnalysis = () => {
    const { teamId, teamData, fetchTeamAnalysis, loading, error, saveTeamId } = useFPL();
    const [viewMode, setViewMode] = useState('pitch'); // 'pitch' or 'list'
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
                <h2 className="text-3xl font-bold text-white mb-2">Team Analysis</h2>
                <p className="text-gray-400 mb-6 max-w-md">Enter your FPL Team ID to view your squad.</p>
                <form onSubmit={handleSearch} className="flex gap-2">
                    <input
                        type="number"
                        placeholder="Team ID"
                        className="bg-gray-800 border border-gray-700 text-white px-4 py-2 rounded-lg focus:outline-none focus:border-purple-500"
                        value={inputId}
                        onChange={(e) => setInputId(e.target.value)}
                    />
                    <button type="submit" className="bg-purple-600 hover:bg-purple-500 text-white px-6 py-2 rounded-lg font-medium transition-colors">
                        View
                    </button>
                </form>
            </div>
        );
    }

    if (loading) return <div className="flex justify-center h-[60vh] items-center text-purple-400"><Loader className="animate-spin mr-2" /> Loading Team Data...</div>;
    if (error) return (
        <div className="flex flex-col items-center justify-center h-[60vh] text-red-400">
            <AlertCircle size={48} className="mb-4" />
            <p>{error}</p>
            <button onClick={() => fetchTeamAnalysis(teamId)} className="mt-4 px-4 py-2 bg-gray-800 rounded hover:bg-gray-700 text-white">Retry</button>
        </div>
    );

    const players = teamData?.players || [];
    // Simple logic to separate Bench: assuming last 4 players of the list are bench if full squad (15)
    // The API should ideally return 'position' or 'is_bench' flag. 
    // If the API returns 'picks' we can map is_bench.
    // teamData.picks has 'is_captain', 'is_vice_captain', 'multiplier', 'position' (1-15)

    // Merge picks info if available
    const picks = teamData?.picks || [];
    const mergedPlayers = players.map(p => {
        const pick = picks.find(pick => pick.element === p.id);
        return {
            ...p,
            position: pick ? pick.position : 99,
            is_captain: pick ? pick.is_captain : false,
            is_vice_captain: pick ? pick.is_vice_captain : false,
            multiplier: pick ? pick.multiplier : 1
        };
    }).sort((a, b) => a.position - b.position);

    const startingXI = mergedPlayers.filter(p => p.position <= 11);
    const bench = mergedPlayers.filter(p => p.position > 11);

    return (
        <div className="space-y-6">
            <header className="flex justify-between items-center mb-6">
                <div>
                    <h2 className="text-2xl font-bold text-white">My Team</h2>
                    <p className="text-gray-400">Gameweek {teamData?.gameweek?.current}</p>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={() => fetchTeamAnalysis(teamId)}
                        className="p-2 text-gray-400 hover:text-white bg-gray-800 rounded-lg"
                        title="Refresh Data"
                    >
                        <RefreshCw size={20} />
                    </button>
                </div>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Left Column: Pitch View */}
                <div className="lg:col-span-2 space-y-8">
                    <PitchView players={startingXI} />

                    <div className="bg-gray-900/50 rounded-xl p-4 border border-gray-800">
                        <h3 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">Bench</h3>
                        <div className="flex justify-center space-x-4 sm:space-x-8">
                            {bench.map(p => (
                                <div key={p.id} className="text-center group relative cursor-pointer">
                                    <div className="w-10 h-10 rounded-full flex items-center justify-center bg-gray-800 border border-gray-600 group-hover:border-purple-500">
                                        <img
                                            src={`https://resources.premierleague.com/premierleague/photos/players/110x140/p${p.code}.png`}
                                            alt={p.web_name}
                                            className="w-full h-full object-cover rounded-full opacity-75 group-hover:opacity-100"
                                            onError={(e) => { e.target.style.display = 'none'; e.target.parentElement.innerText = p.web_name?.substring(0, 2) }}
                                        />
                                    </div>
                                    <p className="text-[10px] mt-1 text-gray-400 group-hover:text-white truncate max-w-[60px]">{p.web_name}</p>
                                    <p className="text-[9px] text-green-500">{p.pred_points?.toFixed(1)} xP</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Right Column: Stats & Insights */}
                <div className="space-y-6">
                    <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
                        <h3 className="text-lg font-bold text-white mb-4">gw Summary</h3>
                        <div className="space-y-4">
                            <div className="flex justify-between items-center pb-2 border-b border-gray-800">
                                <span className="text-gray-400">Expected Points</span>
                                <span className="text-xl font-bold text-purple-400">
                                    {startingXI.reduce((acc, p) => acc + (p.pred_points * (p.multiplier || 1)), 0).toFixed(1)}
                                </span>
                            </div>
                            <div className="flex justify-between items-center pb-2 border-b border-gray-800">
                                <span className="text-gray-400">Team Value</span>
                                <span className="font-medium text-white">
                                    £{(mergedPlayers.reduce((acc, p) => acc + p.now_cost, 0) / 10).toFixed(1)}m
                                </span>
                            </div>
                        </div>
                    </div>

                    <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
                        <h3 className="text-lg font-bold text-white mb-4">Captaincy</h3>
                        <div className="flex items-center space-x-4 p-3 bg-purple-900/20 border border-purple-500/30 rounded-lg">
                            <div className="w-10 h-10 rounded-full bg-purple-500 flex items-center justify-center text-white font-bold text-lg">C</div>
                            <div>
                                <p className="text-sm font-bold text-white">
                                    {startingXI.find(p => p.is_captain)?.web_name || '-'}
                                </p>
                                <p className="text-xs text-purple-300">Top Predicted Scorer</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default TeamAnalysis;
