import React, { createContext, useContext, useState, useEffect } from 'react';
import { fplService } from '../services/api';

const FPLContext = createContext();

export const FPLProvider = ({ children }) => {
    const [teamId, setTeamId] = useState(() => localStorage.getItem('fpl_team_id') || '');
    const [teamData, setTeamData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [bootstrap, setBootstrap] = useState(null);
    const [settings, setSettings] = useState(null);
    const [generalData, setGeneralData] = useState(null);

    // Load Bootstrap Data on Mount
    useEffect(() => {
        const fetchBootstrap = async () => {
            try {
                const res = await fplService.getBootstrap();
                setBootstrap(res.data);
            } catch (err) {
                console.error("Failed to load bootstrap data", err);
            }
        };

        const fetchGeneralData = async () => {
            // Only fetch if we don't have it (or force refresh if needed later)
            try {
                const res = await fplService.getGeneralData();
                setGeneralData(res.data);
            } catch (err) {
                console.error("Failed to load general data", err);
            }
        };

        fetchBootstrap();
        fetchGeneralData();
    }, []);

    const saveTeamId = (id) => {
        setTeamId(id);
        localStorage.setItem('fpl_team_id', id);
        // Also fetch settings when team ID changes
        if (id) fetchSettings(id);
    };

    const fetchSettings = async (id) => {
        try {
            const res = await fplService.getSettings(id);
            if (res.data && res.data.team_id) {
                setSettings(res.data);
            }
        } catch (err) {
            console.error("Failed to load user settings", err);
        }
    };

    const updateSettings = async (newSettings) => {
        try {
            // Optimistic update
            setSettings({ ...settings, ...newSettings });
            await fplService.saveSettings({
                team_id: teamId,
                ...newSettings
            });
        } catch (err) {
            console.error("Failed to save settings", err);
            // Revert or show error
        }
    };

    const fetchTeamAnalysis = async (id = teamId) => {
        if (!id) return;
        setLoading(true);
        setError(null);
        try {
            const response = await fplService.analyzeTeam(id);
            setTeamData(response.data);
            // If successfully fetched, ensure ID is saved
            if (id !== teamId) saveTeamId(id);
        } catch (err) {
            console.error(err);
            setError(err.message || 'Failed to fetch team data');
        } finally {
            setLoading(false);
        }
    };

    // Load settings on init if teamId exists
    useEffect(() => {
        if (teamId) fetchSettings(teamId);
    }, [teamId]);

    const value = {
        teamId,
        saveTeamId,
        teamData,
        fetchTeamAnalysis,
        startSimulation: fplService.simulateTeam,
        loading,
        error,
        bootstrap,
        settings,
        generalData,
        updateSettings,
        fplService
    };

    return (
        <FPLContext.Provider value={value}>
            {children}
        </FPLContext.Provider>
    );
};

export const useFPL = () => useContext(FPLContext);
