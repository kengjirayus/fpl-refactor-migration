import React from 'react';

const PitchView = ({ players }) => {
    if (!players || players.length === 0) {
        return (
            <div className="w-full h-[600px] bg-green-800/20 rounded-xl flex items-center justify-center border border-green-700/30">
                <p className="text-green-400">No players to display</p>
            </div>
        );
    }

    // Filter Starting XI (1-11) - usually first 11 if sorted, but safe to assume 1-11 in response
    // The API returns 'players' which seems to include bench? 
    // Let's assume input 'players' is already the Starting XI for the pitch 
    // OR we filter by 'position' if we had that info. 
    // For now, let's assume the parent passes the Starting XI.

    // Group by element_type (1=GKP, 2=DEF, 3=MID, 4=FWD)
    const gkp = players.filter(p => p.element_type === 1);
    const def = players.filter(p => p.element_type === 2);
    const mid = players.filter(p => p.element_type === 3);
    const fwd = players.filter(p => p.element_type === 4);

    const PlayerCard = ({ player }) => {
        // Color coding for difficulty or form could go here
        const isCaptain = player.is_captain;
        const isVice = player.is_vice_captain;

        return (
            <div className="flex flex-col items-center justify-center w-20 sm:w-24 group cursor-pointer relative">
                <div className={`
                w-10 h-10 sm:w-12 sm:h-12 rounded-full flex items-center justify-center 
                bg-gradient-to-br from-gray-700 to-gray-800 shadow-lg border-2
                ${player.chance_of_playing_next_round !== 100 && player.chance_of_playing_next_round !== null ? 'border-yellow-500' : 'border-gray-600'}
                group-hover:border-purple-500 transition-all duration-300 relative
            `}>
                    <img
                        src={`https://resources.premierleague.com/premierleague/photos/players/110x140/p${player.code}.png`}
                        alt={player.web_name}
                        className="w-full h-full object-cover rounded-full opacity-90 group-hover:opacity-100"
                        onError={(e) => { e.target.style.display = 'none'; e.target.parentElement.innerText = player.web_name?.substring(0, 2) }}
                    />
                    {/* Captain Armband */}
                    {(isCaptain || isVice) && (
                        <div className="absolute -top-2 -right-2 w-5 h-5 bg-black text-white text-[10px] font-bold rounded-full flex items-center justify-center border border-white">
                            {isCaptain ? 'C' : 'V'}
                        </div>
                    )}
                </div>

                <div className="mt-1 text-center bg-gray-900/80 backdrop-blur-sm px-2 py-0.5 rounded-md border border-gray-700/50 group-hover:bg-purple-900/80 group-hover:border-purple-500/50 transition-colors">
                    <p className="text-[10px] sm:text-xs font-bold text-white truncate max-w-[80px]">{player.web_name}</p>
                    <p className="text-[9px] sm:text-[10px] text-green-400 font-mono">{player.pred_points?.toFixed(1)} xP</p>
                </div>

                {/* Tooltip */}
                <div className="absolute bottom-16 opacity-0 group-hover:opacity-100 transition-opacity duration-200 bg-black/90 p-2 rounded-lg pointer-events-none z-20 w-32 border border-gray-700 text-center">
                    <p className="font-bold text-xs text-white">{player.web_name}</p>
                    <p className="text-[10px] text-gray-400">{player.team_short} • £{player.now_cost / 10}m</p>
                    <div className="mt-1 flex justify-between text-[10px] text-gray-300">
                        <span>Fix: {player.opponent_str || '-'}</span>
                        <span>Form: {player.form}</span>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="w-full relative aspect-[2/3] sm:aspect-[3/4] md:aspect-auto md:h-[700px] overflow-hidden rounded-xl bg-gradient-to-b from-green-900 to-emerald-950 border-4 border-emerald-900/50 shadow-2xl">
            {/* Pitch Markings */}
            <div className="absolute inset-4 border-2 border-white/20 rounded-sm pointer-events-none"></div>
            <div className="absolute top-0 left-1/4 right-1/4 h-16 border-b-2 border-x-2 border-white/20 pointer-events-none"></div>
            <div className="absolute bottom-0 left-1/4 right-1/4 h-16 border-t-2 border-x-2 border-white/20 pointer-events-none"></div>
            <div className="absolute top-1/2 left-0 right-0 h-px bg-white/20 pointer-events-none"></div>
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-32 h-32 rounded-full border-2 border-white/20 pointer-events-none"></div>

            {/* Rows */}
            <div className="absolute inset-0 flex flex-col justify-between py-8 px-4 z-10">
                {/* GKP */}
                <div className="flex justify-center items-center h-1/5">
                    {gkp.map(p => <PlayerCard key={p.id} player={p} />)}
                </div>
                {/* DEF */}
                <div className="flex justify-center items-center space-x-4 sm:space-x-8 h-1/4">
                    {def.map(p => <PlayerCard key={p.id} player={p} />)}
                </div>
                {/* MID */}
                <div className="flex justify-center items-center space-x-4 sm:space-x-8 h-1/4">
                    {mid.map(p => <PlayerCard key={p.id} player={p} />)}
                </div>
                {/* FWD */}
                <div className="flex justify-center items-center space-x-6 sm:space-x-12 h-1/5">
                    {fwd.map(p => <PlayerCard key={p.id} player={p} />)}
                </div>
            </div>
        </div>
    );
};

export default PitchView;
