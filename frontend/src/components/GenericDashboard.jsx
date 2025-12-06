
import React from 'react';
import { useFPL } from '../context/FPLContext';

const GenericDashboard = () => {
    const { generalData, loading, error } = useFPL();

    if (loading && !generalData) return <div className="text-center p-10 text-white animate-pulse">Loading FPL Data...</div>;
    if (error) return <div className="text-red-500 p-10 text-center">Error: {error}</div>;
    if (!generalData) return <div className="text-center p-10 text-gray-400">Initializing Dashboard...</div>;

    const { gameweek, top_players, captains, risers, fallers, fixture_difficulty, understat_players, understat_teams, top_form, differentials, top_selected, opponent_matrix, teams } = generalData;

    const formatThaiDate = (dateString) => {
        if (!dateString) return "-";
        return new Date(dateString).toLocaleString('th-TH', {
            timeZone: 'Asia/Bangkok',
            calendar: 'gregory',
            weekday: 'long',
            day: 'numeric',
            month: 'long',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    return (
        <div className="space-y-8 animate-fade-in">
            <div className="bg-gradient-to-r from-purple-900 to-indigo-900 rounded-xl p-6 text-white shadow-lg">
                <div className="flex flex-col md:flex-row justify-between items-center gap-4">
                    <div>
                        <h1 className="text-3xl font-bold mb-1">Gameweek {gameweek?.current}</h1>
                        <p className="text-purple-200">Next: Gameweek {gameweek?.next}</p>
                    </div>
                    <div className="text-center md:text-right bg-white/10 p-3 rounded-lg backdrop-blur-sm border border-white/10">
                        <div className="text-xs text-purple-200 uppercase tracking-wider mb-1">Deadline (Thailand)</div>
                        <div className="text-xl font-bold text-yellow-400">
                            {formatThaiDate(gameweek?.deadline_time)}
                        </div>
                    </div>
                </div>
            </div>

            {/* Top Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white dark:bg-gray-800 p-4 rounded-xl shadow-md text-gray-900 dark:text-white">
                    <h3 className="text-lg font-bold mb-4 border-b pb-2 border-gray-200 dark:border-gray-700">👑 5 สุดยอดกัปตัน</h3>
                    <div className="space-y-3">
                        {captains.slice(0, 5).map(player => (
                            <div key={player.id} className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 bg-gray-200 rounded-full overflow-hidden">
                                        <img src={player.photo_url?.replace('p-blank', 'p-blank') || `https://resources.premierleague.com/premierleague/photos/players/110x140/p${player.code}.png`}
                                            alt={player.web_name}
                                            className="w-full h-full object-cover"
                                            onError={(e) => { e.target.src = "https://resources.premierleague.com/premierleague/photos/players/110x140/p-blank.png" }}
                                        />
                                    </div>
                                    <div>
                                        <div className="font-semibold text-gray-900 dark:text-white">{player.web_name}</div>
                                        <div className="text-xs text-gray-500 dark:text-gray-400">
                                            {player.next_opponent || '-'}
                                        </div>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="font-bold text-purple-600">{player.pred_points.toFixed(1)} <span className="text-xs text-gray-400">pts</span></div>
                                    <div className="text-xs text-gray-500">£{(player.now_cost / 10).toFixed(1)}m</div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="bg-white dark:bg-gray-800 p-4 rounded-xl shadow-md text-gray-900 dark:text-white">
                    <h3 className="text-lg font-bold mb-4 border-b pb-2 border-gray-200 dark:border-gray-700">💹 ราคากำลังขึ้น 🔼</h3>
                    <div className="space-y-3">
                        {risers.slice(0, 5).map(player => (
                            <div key={player.id} className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 bg-gray-200 rounded-full overflow-hidden">
                                        <img src={player.photo_url?.replace('p-blank', 'p-blank') || `https://resources.premierleague.com/premierleague/photos/players/110x140/p${player.code}.png`}
                                            alt={player.web_name}
                                            className="w-full h-full object-cover"
                                            onError={(e) => { e.target.src = "https://resources.premierleague.com/premierleague/photos/players/110x140/p-blank.png" }}
                                        />
                                    </div>
                                    <div className="font-medium text-gray-900 dark:text-gray-100">{player.web_name}</div>
                                </div>
                                <div className="text-right">
                                    <div className="text-green-500 font-bold">+£{(player.cost_change_start / 10).toFixed(1)}m</div>
                                    <div className="text-xs text-gray-500">£{(player.now_cost / 10).toFixed(1)}m</div>
                                </div>
                            </div>
                        ))}
                        {risers.length === 0 && <div className="text-gray-500 italic">No significant risers yet.</div>}
                    </div>
                </div>

                <div className="bg-white dark:bg-gray-800 p-4 rounded-xl shadow-md text-gray-900 dark:text-white">
                    <h3 className="text-lg font-bold mb-4 border-b pb-2 border-gray-200 dark:border-gray-700">🔻 ราคากำลังลง 📉</h3>
                    <div className="space-y-3">
                        {fallers.slice(0, 5).map(player => (
                            <div key={player.id} className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 bg-gray-200 rounded-full overflow-hidden">
                                        <img src={player.photo_url?.replace('p-blank', 'p-blank') || `https://resources.premierleague.com/premierleague/photos/players/110x140/p${player.code}.png`}
                                            alt={player.web_name}
                                            className="w-full h-full object-cover"
                                            onError={(e) => { e.target.src = "https://resources.premierleague.com/premierleague/photos/players/110x140/p-blank.png" }}
                                        />
                                    </div>
                                    <div className="font-medium text-gray-900 dark:text-gray-100">{player.web_name}</div>
                                </div>
                                <div className="text-right">
                                    <div className="text-red-500 font-bold">£{(player.cost_change_start / 10).toFixed(1)}m</div>
                                    <div className="text-xs text-gray-500">£{(player.now_cost / 10).toFixed(1)}m</div>
                                </div>
                            </div>
                        ))}
                        {fallers.length === 0 && <div className="text-gray-500 italic">No significant fallers yet.</div>}
                    </div>
                </div>
            </div>

            {/* Top 20 Players Table */}
            <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-md text-gray-900 dark:text-white">
                <div className="mb-4">
                    <h3 className="text-xl font-bold">⭐ Top 20 นักเตะคะแนนคาดการณ์สูงสุด</h3>
                    <p className="text-xs text-gray-500 mt-1">
                        ℹ️ <strong>Range</strong>: ช่วงคะแนนที่คาดว่าจะทำได้ (ต่ำสุด - สูงสุด) | <strong>Risk</strong>: ความเสี่ยง (🟢 ต่ำ, 🟡 ปานกลาง, 🔴 สูง)
                    </p>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
                            <tr>
                                <th className="px-4 py-3 text-center">#</th>
                                <th className="px-4 py-3">รูป</th>
                                <th className="px-4 py-3">ชื่อนักเตะ</th>
                                <th className="px-4 py-3 text-center">ทีม</th>
                                <th className="px-4 py-3 text-center">ตำแหน่ง</th>
                                <th className="px-4 py-3 text-center">ราคา</th>
                                <th className="px-4 py-3 text-center">xMins</th>
                                <th className="px-4 py-3 text-center">ฟอร์ม</th>
                                <th className="px-4 py-3 text-center">ความง่าย</th>
                                <th className="px-4 py-3 text-center bg-gray-100 dark:bg-gray-600">คะแนนคาดการณ์</th>
                                <th className="px-4 py-3 text-center">Range</th>
                                <th className="px-4 py-3 text-center">Risk</th>
                            </tr>
                        </thead>
                        <tbody>
                            {top_players.slice(0, 20).map((player, index) => {
                                // Formatting Logic
                                const posMap = { 1: 'GK', 2: 'DEF', 3: 'MID', 4: 'FWD' };
                                const pos = posMap[player.element_type] || '-';
                                const price = `£${(player.now_cost / 10).toFixed(1)}m`;
                                const roleIcon = player.set_piece_roles?.length > 0 ? ' 🎯' : '';
                                const formDisplay = player.weighted_form ? `${parseFloat(player.weighted_form).toFixed(1)} ${player.form_trend || ''}` : player.form || '-';
                                const fixtureEase = parseFloat(player.avg_fixture_ease || 0).toFixed(2);
                                const riskMap = { 'LOW': '🟢 Low', 'MEDIUM': '🟡 Med', 'HIGH': '🔴 High' };
                                const riskDisplay = riskMap[player.risk_level] || player.risk_level || '-';
                                const rangeDisplay = (player.floor !== undefined && player.ceiling !== undefined)
                                    ? `${player.floor.toFixed(1)} - ${player.ceiling.toFixed(1)}`
                                    : '-';

                                return (
                                    <tr key={player.id} className="bg-white border-b dark:bg-gray-800 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600">
                                        <td className="px-4 py-4 text-center font-bold text-gray-500">{index + 1}</td>
                                        <td className="px-4 py-4">
                                            <div className="w-10 h-12 bg-gray-200 rounded overflow-hidden mx-auto">
                                                <img src={player.photo_url?.replace('p-blank', 'p-blank') || `https://resources.premierleague.com/premierleague/photos/players/110x140/p${player.code}.png`}
                                                    alt={player.web_name}
                                                    className="w-full h-full object-cover"
                                                    onError={(e) => { e.target.src = "https://resources.premierleague.com/premierleague/photos/players/110x140/p-blank.png" }}
                                                />
                                            </div>
                                        </td>
                                        <td className="px-4 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white">
                                            {player.web_name}{roleIcon}
                                        </td>
                                        <td className="px-4 py-4 text-center">{player.team_short}</td>
                                        <td className="px-4 py-4 text-center">
                                            <span className={`px-2 py-1 rounded text-xs font-bold 
                                                ${pos === 'GK' ? 'bg-yellow-100 text-yellow-800' :
                                                    pos === 'DEF' ? 'bg-blue-100 text-blue-800' :
                                                        pos === 'MID' ? 'bg-green-100 text-green-800' :
                                                            'bg-red-100 text-red-800'}`}>
                                                {pos}
                                            </span>
                                        </td>
                                        <td className="px-4 py-4 text-center">{price}</td>
                                        <td className="px-4 py-4 text-center">{player.xMins ? Math.round(player.xMins) : '-'}</td>
                                        <td className="px-4 py-4 text-center">{formDisplay}</td>
                                        <td className="px-4 py-4 text-center">{fixtureEase}</td>
                                        <td className="px-4 py-4 text-center font-bold text-purple-600 bg-gray-50 dark:bg-gray-700">
                                            {player.pred_points.toFixed(1)}
                                        </td>
                                        <td className="px-4 py-4 text-center text-xs text-gray-500">{rangeDisplay}</td>
                                        <td className="px-4 py-4 text-center text-xs">{riskDisplay}</td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Understat Statistics Section */}
            {/* Understat Statistics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Top 5 xG */}
                <div className="bg-white dark:bg-gray-800 p-4 rounded-xl shadow-md text-gray-900 dark:text-white">
                    <h3 className="text-lg font-bold mb-4 border-b pb-2 border-gray-200 dark:border-gray-700">🎯 Top 5 xG (โอกาสยิง)</h3>
                    <div className="space-y-3">
                        {understat_players?.slice().sort((a, b) => b.xG - a.xG).slice(0, 5).map(player => (
                            <div key={player.id} className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 bg-gray-200 rounded-full overflow-hidden">
                                        <img src={player.photo_url?.replace('p-blank', 'p-blank') || "https://resources.premierleague.com/premierleague/photos/players/110x140/p-blank.png"}
                                            alt={player.player_name}
                                            className="w-full h-full object-cover"
                                            onError={(e) => { e.target.src = "https://resources.premierleague.com/premierleague/photos/players/110x140/p-blank.png" }}
                                        />
                                    </div>
                                    <div>
                                        <div className="font-semibold text-gray-900 dark:text-white text-sm">{player.player_name}</div>
                                        <div className="text-xs text-gray-500 dark:text-gray-400">{player.team_short}</div>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="font-bold text-purple-600">{player.xG.toFixed(2)} <span className="text-xs text-gray-400">xG</span></div>
                                    <div className="text-xs text-gray-500">{player.goals_scored} Goal</div>
                                </div>
                            </div>
                        ))}
                        {(!understat_players || understat_players.length === 0) && <div className="text-xs text-gray-400 italic">ไม่มีข้อมูล xG</div>}
                    </div>
                </div>

                {/* Top 5 xA */}
                <div className="bg-white dark:bg-gray-800 p-4 rounded-xl shadow-md text-gray-900 dark:text-white">
                    <h3 className="text-lg font-bold mb-4 border-b pb-2 border-gray-200 dark:border-gray-700">🅰️ Top 5 xA (โอกาสจ่าย)</h3>
                    <div className="space-y-3">
                        {understat_players?.slice().sort((a, b) => b.xA - a.xA).slice(0, 5).map(player => (
                            <div key={player.id} className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 bg-gray-200 rounded-full overflow-hidden">
                                        <img src={player.photo_url?.replace('p-blank', 'p-blank') || "https://resources.premierleague.com/premierleague/photos/players/110x140/p-blank.png"}
                                            alt={player.player_name}
                                            className="w-full h-full object-cover"
                                            onError={(e) => { e.target.src = "https://resources.premierleague.com/premierleague/photos/players/110x140/p-blank.png" }}
                                        />
                                    </div>
                                    <div>
                                        <div className="font-semibold text-gray-900 dark:text-white text-sm">{player.player_name}</div>
                                        <div className="text-xs text-gray-500 dark:text-gray-400">{player.team_short}</div>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="font-bold text-purple-600">{player.xA.toFixed(2)} <span className="text-xs text-gray-400">xA</span></div>
                                    <div className="text-xs text-gray-500">{player.assists} Assist</div>
                                </div>
                            </div>
                        ))}
                        {(!understat_players || understat_players.length === 0) && <div className="text-xs text-gray-400 italic">ไม่มีข้อมูล xA</div>}
                    </div>
                </div>

                {/* Top 5 xPTS */}
                <div className="bg-white dark:bg-gray-800 p-4 rounded-xl shadow-md text-gray-900 dark:text-white">
                    <h3 className="text-lg font-bold mb-4 border-b pb-2 border-gray-200 dark:border-gray-700">📈 Top 5 xPTS (คะแนนคาดหวัง)</h3>
                    <div className="space-y-3">
                        {understat_teams?.slice().sort((a, b) => b.xpts - a.xpts).slice(0, 5).map(team => (
                            <div key={team.name} className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 bg-white rounded-full flex items-center justify-center shadow-sm overflow-hidden p-1">
                                        <img src={team.logo_url}
                                            alt={team.name}
                                            className="w-full h-full object-contain"
                                        />
                                    </div>
                                    <div>
                                        <div className="font-semibold text-gray-900 dark:text-white text-sm">{team.name}</div>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="font-bold text-purple-600">{team.xpts.toFixed(2)} <span className="text-xs text-gray-400">xPTS</span></div>
                                </div>
                            </div>
                        ))}
                        {(!understat_teams || understat_teams.length === 0) && <div className="text-xs text-gray-400 italic">ไม่มีข้อมูล xPTS</div>}
                    </div>
                </div>
            </div>

            {/* Player Trend Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Top 5 Form */}
                <div className="bg-white dark:bg-gray-800 p-4 rounded-xl shadow-md text-gray-900 dark:text-white">
                    <h3 className="text-lg font-bold mb-4 border-b pb-2 border-gray-200 dark:border-gray-700">🔥 Top 5 ฟอร์มแรง</h3>
                    <div className="space-y-3">
                        {top_form?.slice(0, 5).map(player => (
                            <div key={player.id} className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 bg-gray-200 rounded-full overflow-hidden">
                                        <img src={player.photo_url?.replace('p-blank', 'p-blank') || "https://resources.premierleague.com/premierleague/photos/players/110x140/p-blank.png"}
                                            alt={player.web_name}
                                            className="w-full h-full object-cover"
                                            onError={(e) => { e.target.src = "https://resources.premierleague.com/premierleague/photos/players/110x140/p-blank.png" }}
                                        />
                                    </div>
                                    <div>
                                        <div className="font-semibold text-gray-900 dark:text-white text-sm">{player.web_name}</div>
                                        <div className="text-xs text-gray-500 dark:text-gray-400">{player.team_short}</div>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="font-bold text-orange-500">{parseFloat(player.form).toFixed(1)}</div>
                                    <div className="text-xs text-gray-500">Form</div>
                                </div>
                            </div>
                        ))}
                        {(!top_form || top_form.length === 0) && <div className="text-xs text-gray-400 italic">ไม่มีข้อมูลฟอร์ม</div>}
                    </div>
                </div>

                {/* Top 5 Differentials (<10%) */}
                <div className="bg-white dark:bg-gray-800 p-4 rounded-xl shadow-md text-gray-900 dark:text-white">
                    <h3 className="text-lg font-bold mb-4 border-b pb-2 border-gray-200 dark:border-gray-700">💎 Top 5 ตัวแรร์ ({'<'}10%)</h3>
                    <div className="space-y-3">
                        {differentials?.slice(0, 5).map(player => (
                            <div key={player.id} className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 bg-gray-200 rounded-full overflow-hidden">
                                        <img src={player.photo_url?.replace('p-blank', 'p-blank') || "https://resources.premierleague.com/premierleague/photos/players/110x140/p-blank.png"}
                                            alt={player.web_name}
                                            className="w-full h-full object-cover"
                                            onError={(e) => { e.target.src = "https://resources.premierleague.com/premierleague/photos/players/110x140/p-blank.png" }}
                                        />
                                    </div>
                                    <div>
                                        <div className="font-semibold text-gray-900 dark:text-white text-sm">{player.web_name}</div>
                                        <div className="text-xs text-gray-500 dark:text-gray-400">{player.team_short}</div>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="font-bold text-blue-500">{player.selected_by_percent}%</div>
                                    <div className="text-xs text-gray-500">Selected</div>
                                </div>
                            </div>
                        ))}
                        {(!differentials || differentials.length === 0) && <div className="text-xs text-gray-400 italic">ไม่มีข้อมูลตัวแรร์</div>}
                    </div>
                </div>

                {/* Top 5 Most Selected */}
                <div className="bg-white dark:bg-gray-800 p-4 rounded-xl shadow-md text-gray-900 dark:text-white">
                    <h3 className="text-lg font-bold mb-4 border-b pb-2 border-gray-200 dark:border-gray-700">👥 Top 5 ขวัญใจมหาชน</h3>
                    <div className="space-y-3">
                        {top_selected?.slice(0, 5).map(player => (
                            <div key={player.id} className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 bg-gray-200 rounded-full overflow-hidden">
                                        <img src={player.photo_url?.replace('p-blank', 'p-blank') || "https://resources.premierleague.com/premierleague/photos/players/110x140/p-blank.png"}
                                            alt={player.web_name}
                                            className="w-full h-full object-cover"
                                            onError={(e) => { e.target.src = "https://resources.premierleague.com/premierleague/photos/players/110x140/p-blank.png" }}
                                        />
                                    </div>
                                    <div>
                                        <div className="font-semibold text-gray-900 dark:text-white text-sm">{player.web_name}</div>
                                        <div className="text-xs text-gray-500 dark:text-gray-400">{player.team_short}</div>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="font-bold text-green-500">{player.selected_by_percent}%</div>
                                    <div className="text-xs text-gray-500">Selected</div>
                                </div>
                            </div>
                        ))}
                        {(!top_selected || top_selected.length === 0) && <div className="text-xs text-gray-400 italic">ไม่มีข้อมูล</div>}
                    </div>
                </div>
            </div>

            {/* Fixture Planner Section */}
            <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-md text-gray-900 dark:text-white">
                <h3 className="text-xl font-bold mb-4">🗓️ ตารางแข่ง 5 นัดล่วงหน้า (Fixture Planner)</h3>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-center border-collapse">
                        <thead>
                            <tr className="bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300">
                                <th className="p-3 border dark:border-gray-600 text-left">Team</th>
                                {fixture_difficulty && fixture_difficulty.length > 0 && Object.keys(fixture_difficulty[0])
                                    .filter(key => key.startsWith('GW'))
                                    .sort((a, b) => parseInt(a.replace('GW', '')) - parseInt(b.replace('GW', '')))
                                    .map(gw => <th key={gw} className="p-3 border dark:border-gray-600 min-w-[60px]">{gw}</th>)
                                }
                            </tr>
                        </thead>
                        <tbody>
                            {fixture_difficulty
                                ?.map(teamRow => {
                                    // Calculate Total Difficulty for sorting (Higher Sum = Easier on average if using strict > 0 logic)
                                    // Wait, logic is: >=15 Easy, >=8 Medium. So High Value = Easy.
                                    // Summing them gives "Easiness Score".
                                    const gwKeys = Object.keys(teamRow).filter(key => key.startsWith('GW'));
                                    const totalScore = gwKeys.reduce((acc, key) => acc + (teamRow[key] || 0), 0);
                                    return { ...teamRow, totalScore, gwKeys };
                                })
                                .sort((a, b) => b.totalScore - a.totalScore) // Descending Sort (Most Easy First)
                                .map((teamRow) => {
                                    const teamShort = teamRow.team_short;
                                    const oppRow = opponent_matrix?.find(o => o.team_short === teamShort) || {};
                                    const teamInfo = teams?.find(t => t.short_name === teamShort);

                                    return (
                                        <tr key={teamShort} className="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700">
                                            <td className="p-2 font-bold bg-gray-50 dark:bg-gray-800 border-r dark:border-gray-600 text-left whitespace-nowrap">
                                                <div className="flex items-center gap-2">
                                                    {teamInfo?.logo_url && (
                                                        <img src={teamInfo.logo_url} alt={teamShort} className="w-6 h-6 object-contain" />
                                                    )}
                                                    <div>
                                                        <div>{teamShort}</div>
                                                        <div className="text-[10px] text-gray-500 font-normal">อันดับ {teamInfo?.position || '-'}</div>
                                                    </div>
                                                </div>
                                            </td>
                                            {teamRow.gwKeys
                                                .sort((a, b) => parseInt(a.replace('GW', '')) - parseInt(b.replace('GW', '')))
                                                .map(gw => {
                                                    const diff = teamRow[gw];
                                                    const opp = oppRow[gw] || '-';

                                                    // Color Logic (Higher is Easier)
                                                    let bgClass = "bg-gray-500 text-white"; // Default Blank
                                                    if (diff >= 15) bgClass = "bg-[#35F00A] text-black"; // Easy (Lime)
                                                    else if (diff >= 8) bgClass = "bg-[#FFF100] text-black"; // Medium (Yellow)
                                                    else if (diff > 0) bgClass = "bg-[#FF0000] text-white"; // Hard (Red)

                                                    return (
                                                        <td key={gw} className={`p-2 border dark:border-gray-600 ${bgClass} font-semibold align-middle`}>
                                                            <div className="text-xs">{opp}</div>
                                                        </td>
                                                    );
                                                })
                                            }
                                        </tr>
                                    );
                                })}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default GenericDashboard;
