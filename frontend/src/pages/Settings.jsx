import React from 'react';
import { useFPL } from '../context/FPLContext';
import { Save, Settings as SettingsIcon } from 'lucide-react';

const Settings = () => {
    const { teamId, settings, updateSettings } = useFPL();

    const handleSave = (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        updateSettings({
            email: formData.get('email'),
            theme: formData.get('theme')
        });
        alert("Settings Saved!");
    };

    if (!teamId) {
        return <div className="text-white text-center mt-20">Please login / enter Team ID first.</div>;
    }

    return (
        <div className="max-w-2xl mx-auto space-y-8">
            <header className="flex items-center gap-3 mb-8 border-b border-gray-700 pb-4">
                <SettingsIcon className="text-purple-500" size={32} />
                <h2 className="text-2xl font-bold text-white">User Settings</h2>
            </header>

            <form onSubmit={handleSave} className="space-y-6">
                <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-2">Team ID</label>
                            <input
                                type="text"
                                value={teamId}
                                disabled
                                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-gray-500 cursor-not-allowed"
                            />
                            <p className="text-xs text-gray-600 mt-1">Managed automatically</p>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-2">Email (Optional)</label>
                            <input
                                name="email"
                                type="email"
                                defaultValue={settings?.email || ''}
                                placeholder="For notifications..."
                                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-purple-500"
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-400 mb-2">Appearance</label>
                        <select
                            name="theme"
                            defaultValue={settings?.theme || 'dark'}
                            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-purple-500"
                        >
                            <option value="dark">Dark Mode (Default)</option>
                            <option value="light">Light Mode</option>
                        </select>
                    </div>
                </div>

                <div className="flex justify-end">
                    <button type="submit" className="flex items-center gap-2 bg-purple-600 hover:bg-purple-500 text-white px-6 py-2.5 rounded-lg font-bold shadow-lg transition-all">
                        <Save size={18} /> Save Settings
                    </button>
                </div>
            </form>
        </div>
    );
};

export default Settings;
