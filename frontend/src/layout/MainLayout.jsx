import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
    LayoutDashboard,
    Shirt,
    ArrowLeftRight,
    BarChart2,
    Zap,
    Settings,
    Menu,
    X
} from 'lucide-react';

const SidebarItem = ({ icon: Icon, label, path, active }) => {
    return (
        <Link
            to={path}
            className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 group ${active
                    ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-lg shadow-indigo-500/30'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                }`}
        >
            <Icon size={20} className={`${active ? 'text-white' : 'text-gray-500 group-hover:text-white'} transition-colors`} />
            <span className="font-medium">{label}</span>
        </Link>
    );
};

const MainLayout = ({ children }) => {
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const location = useLocation();

    const navItems = [
        { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
        { icon: Shirt, label: 'My Team', path: '/team' },
        { icon: ArrowLeftRight, label: 'Transfers', path: '/transfers' },
        { icon: BarChart2, label: 'Analysis', path: '/analysis' },
        { icon: Zap, label: 'Simulation', path: '/simulation' },
        { icon: Settings, label: 'Settings', path: '/settings' },
    ];

    return (
        <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden font-sans">
            {/* Sidebar - Desktop */}
            <aside className="hidden md:flex flex-col w-64 border-r border-gray-800 bg-gray-900/50 backdrop-blur-xl">
                <div className="p-6">
                    <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
                        FPL WIZ
                    </h1>
                    <p className="text-xs text-gray-500 mt-1">AI-Powered Assistant</p>
                </div>

                <nav className="flex-1 px-3 space-y-1 overflow-y-auto">
                    {navItems.map((item) => (
                        <SidebarItem
                            key={item.path}
                            icon={item.icon}
                            label={item.label}
                            path={item.path}
                            active={location.pathname === item.path}
                        />
                    ))}
                </nav>

                <div className="p-4 border-t border-gray-800">
                    <div className="flex items-center space-x-3 p-2 rounded-lg bg-gray-800/50">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-yellow-400 to-orange-500 flex items-center justify-center text-xs font-bold text-black">
                            KJ
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-white truncate">Kengji</p>
                            <p className="text-xs text-gray-500 truncate">FPL Manager</p>
                        </div>
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
                {/* Mobile Header */}
                <header className="md:hidden flex items-center justify-between p-4 border-b border-gray-800 bg-gray-900">
                    <h1 className="text-xl font-bold text-white">FPL WIZ</h1>
                    <button
                        onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                        className="p-2 text-gray-400 hover:text-white"
                    >
                        {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
                    </button>
                </header>

                {/* Mobile Sidebar Overlay */}
                {isMobileMenuOpen && (
                    <div className="fixed inset-0 z-50 bg-gray-900 md:hidden">
                        <div className="flex flex-col h-full p-4">
                            <div className="flex items-center justify-between mb-8">
                                <h2 className="text-2xl font-bold text-white">Menu</h2>
                                <button
                                    onClick={() => setIsMobileMenuOpen(false)}
                                    className="p-2 text-gray-400 hover:text-white"
                                >
                                    <X size={24} />
                                </button>
                            </div>
                            <nav className="space-y-2">
                                {navItems.map((item) => (
                                    <div key={item.path} onClick={() => setIsMobileMenuOpen(false)}>
                                        <SidebarItem
                                            icon={item.icon}
                                            label={item.label}
                                            path={item.path}
                                            active={location.pathname === item.path}
                                        />
                                    </div>
                                ))}
                            </nav>
                        </div>
                    </div>
                )}

                {/* Content Area */}
                <main className="flex-1 overflow-y-auto p-4 md:p-8 scrollbar-hide relative">
                    {/* Background Gradient Blob */}
                    <div className="fixed top-0 left-0 w-full h-full pointer-events-none z-0 overflow-hidden">
                        <div className="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] bg-purple-600/10 rounded-full blur-[100px]" />
                        <div className="absolute bottom-[-10%] left-[-10%] w-[600px] h-[600px] bg-indigo-600/10 rounded-full blur-[120px]" />
                    </div>

                    <div className="relative z-10">
                        {children}
                    </div>
                </main>
            </div>
        </div>
    );
};

export default MainLayout;
