import React, { useState, useEffect, useCallback } from 'react';
import {
    Plus, Trash2, Edit2, Save, Search,
    Loader2, RefreshCw, ToggleLeft, ToggleRight,
    BookOpen, AlertCircle, Check, XCircle, ArrowLeft
} from 'lucide-react';
import api from '../services/api';

const HotWordsPage = ({ adminPassword, setActiveTab, theme }) => {
    const [activeTab, setActiveLocalTab] = useState('entries'); // 'entries' | 'categories'
    const [entries, setEntries] = useState([]);
    const [categories, setCategories] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedCategory, setSelectedCategory] = useState('all');

    // Edit state
    const [editingWord, setEditingWord] = useState(null);
    const [editForm, setEditForm] = useState({ annotation: '', aliases: '' });
    const [isAddingNew, setIsAddingNew] = useState(false);
    const [newEntry, setNewEntry] = useState({
        word: '',
        annotation: '',
        aliases: '',
        category: 'custom'
    });
    const [actionLoading, setActionLoading] = useState(null);

    // Load data
    const loadData = useCallback(async () => {
        if (!adminPassword) return;

        setIsLoading(true);
        setError('');

        try {
            const [entriesRes, categoriesRes] = await Promise.all([
                api.getHotWordsEntries(adminPassword),
                api.getHotWordsCategories(adminPassword)
            ]);

            if (entriesRes.success) {
                setEntries(entriesRes.data.entries || []);
            }
            if (categoriesRes.success) {
                setCategories(categoriesRes.data.categories || []);
            }
        } catch (err) {
            setError('載入資料失敗');
        } finally {
            setIsLoading(false);
        }
    }, [adminPassword]);

    useEffect(() => {
        if (adminPassword) {
            loadData();
        }
    }, [adminPassword, loadData]);

    // Filter entries
    const filteredEntries = entries.filter(entry => {
        const matchesSearch = !searchQuery ||
            entry.word.toLowerCase().includes(searchQuery.toLowerCase()) ||
            entry.annotation.toLowerCase().includes(searchQuery.toLowerCase()) ||
            entry.aliases?.some(a => a.toLowerCase().includes(searchQuery.toLowerCase()));
        const matchesCategory = selectedCategory === 'all' || entry.category === selectedCategory;
        return matchesSearch && matchesCategory;
    });

    // CRUD handlers
    const handleAddEntry = async () => {
        if (!newEntry.word.trim()) return;

        setActionLoading('add');
        try {
            const data = {
                word: newEntry.word.trim(),
                annotation: newEntry.annotation.trim(),
                aliases: newEntry.aliases.split(',').map(a => a.trim()).filter(Boolean),
                category: newEntry.category
            };

            const response = await api.addHotWord(data, adminPassword);
            if (response.success) {
                await loadData();
                setIsAddingNew(false);
                setNewEntry({ word: '', annotation: '', aliases: '', category: 'custom' });
                setError('');
            }
        } catch (err) {
            setError(err.response?.data?.message || '添加失敗');
        } finally {
            setActionLoading(null);
        }
    };

    const handleStartEdit = (entry) => {
        setEditingWord(entry.word);
        setEditForm({
            annotation: entry.annotation || '',
            aliases: (entry.aliases || []).join(', ')
        });
    };

    const handleSaveEdit = async (word) => {
        setActionLoading(`edit-${word}`);
        try {
            const updates = {
                annotation: editForm.annotation.trim(),
                aliases: editForm.aliases.split(',').map(a => a.trim()).filter(Boolean)
            };

            const response = await api.updateHotWord(word, updates, adminPassword);
            if (response.success) {
                await loadData();
                setEditingWord(null);
                setError('');
            }
        } catch (err) {
            setError(err.response?.data?.message || '更新失敗');
        } finally {
            setActionLoading(null);
        }
    };

    const handleDeleteEntry = async (word) => {
        if (!window.confirm(`確定要刪除「${word}」嗎？`)) return;

        setActionLoading(`delete-${word}`);
        try {
            const response = await api.deleteHotWord(word, adminPassword);
            if (response.success) {
                await loadData();
                setError('');
            }
        } catch (err) {
            setError(err.response?.data?.message || '刪除失敗');
        } finally {
            setActionLoading(null);
        }
    };

    const handleToggleCategory = async (categoryName) => {
        setActionLoading(`toggle-${categoryName}`);
        try {
            const response = await api.toggleHotWordsCategory(categoryName, adminPassword);
            if (response.success) {
                await loadData();
                setError('');
            }
        } catch (err) {
            setError(err.response?.data?.message || '切換失敗');
        } finally {
            setActionLoading(null);
        }
    };

    return (
        <div className="container mx-auto max-w-7xl animate-in fade-in duration-300">
            <div className={`glass-panel p-0 overflow-hidden flex flex-col min-h-[80vh] ${theme === 'dark' ? '' : 'bg-white/80 border-slate-200 shadow-xl'
                }`}>
                {/* Header */}
                <div className={`flex items-center justify-between p-6 border-b shrink-0 ${theme === 'dark' ? 'border-white/10 bg-white/5' : 'border-slate-200 bg-slate-50/50'
                    }`}>
                    <div className="flex items-center gap-4">
                        <button
                            onClick={() => setActiveTab('upload')}
                            className={`p-2 rounded-lg transition-colors ${theme === 'dark' ? 'text-slate-300 hover:text-white hover:bg-white/10' : 'text-slate-500 hover:text-slate-800 hover:bg-slate-200'
                                }`}
                            title="返回"
                        >
                            <ArrowLeft size={24} />
                        </button>
                        <h2 className={`text-2xl font-display font-bold flex items-center gap-3 ${theme === 'dark' ? 'text-white' : 'text-slate-800'
                            }`}>
                            <BookOpen className="text-brand-primary" size={28} />
                            熱詞管理
                        </h2>
                    </div>
                    <div className="flex items-center gap-3">
                        <button
                            onClick={loadData}
                            disabled={isLoading}
                            className={`p-2.5 rounded-lg transition-colors ${theme === 'dark' ? 'text-slate-300 hover:text-white hover:bg-white/10' : 'text-slate-500 hover:text-slate-800 hover:bg-slate-200'
                                }`}
                            title="重新載入"
                        >
                            <RefreshCw size={20} className={isLoading ? 'animate-spin' : ''} />
                        </button>
                        <div className={`text-sm px-4 py-2 rounded-lg ${theme === 'dark' ? 'text-slate-300 bg-white/5' : 'text-slate-600 bg-slate-100'
                            }`}>
                            共 {entries.length} 個詞彙，{categories.filter(c => c.enabled).length}/{categories.length} 個類別已啟用
                        </div>
                    </div>
                </div>

                {/* Tabs */}
                <div className={`flex border-b shrink-0 px-6 ${theme === 'dark' ? 'border-white/10 bg-white/5' : 'border-slate-200 bg-white'
                    }`}>
                    <button
                        className={`px-6 py-4 text-sm font-medium transition-colors border-b-2 ${activeTab === 'entries'
                            ? 'text-brand-primary border-brand-primary'
                            : theme === 'dark'
                                ? 'text-slate-300 border-transparent hover:text-white hover:border-slate-500'
                                : 'text-slate-500 border-transparent hover:text-slate-800 hover:border-slate-300'
                            }`}
                        onClick={() => setActiveLocalTab('entries')}
                    >
                        詞彙列表
                    </button>
                    <button
                        className={`px-6 py-4 text-sm font-medium transition-colors border-b-2 ${activeTab === 'categories'
                            ? 'text-brand-primary border-brand-primary'
                            : theme === 'dark'
                                ? 'text-slate-300 border-transparent hover:text-white hover:border-slate-500'
                                : 'text-slate-500 border-transparent hover:text-slate-800 hover:border-slate-300'
                            }`}
                        onClick={() => setActiveLocalTab('categories')}
                    >
                        類別管理
                    </button>
                </div>

                {/* Error display */}
                {error && (
                    <div className="mx-6 mt-6 p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-3">
                        <AlertCircle size={20} />
                        {error}
                        <button onClick={() => setError('')} className="ml-auto hover:text-red-300">
                            <XCircle size={18} />
                        </button>
                    </div>
                )}

                {/* Content */}
                <div className="flex-1 p-6 overflow-hidden">
                    {isLoading ? (
                        <div className="flex items-center justify-center h-64">
                            <Loader2 size={40} className="animate-spin text-brand-primary" />
                        </div>
                    ) : activeTab === 'entries' ? (
                        <div className="h-full flex flex-col space-y-4">
                            {/* Search and filter */}
                            <div className="flex gap-4 flex-wrap shrink-0 p-1">
                                <div className="flex-1 min-w-[240px] relative">
                                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-300" size={18} />
                                    <input
                                        type="text"
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                        placeholder="搜尋詞彙..."
                                        className={`glass-input w-full pl-12 py-3 ${theme === 'dark' ? '' : 'bg-white border-slate-200 text-slate-800 placeholder:text-slate-400'
                                            }`}
                                    />
                                </div>
                                <div className="w-48">
                                    <select
                                        value={selectedCategory}
                                        onChange={(e) => setSelectedCategory(e.target.value)}
                                        className={`glass-input w-full py-3 ${theme === 'dark' ? '' : 'bg-white border-slate-200 text-slate-800'
                                            }`}
                                    >
                                        <option value="all">所有類別</option>
                                        {categories.map(cat => (
                                            <option key={cat.name} value={cat.name}>{cat.name}</option>
                                        ))}
                                    </select>
                                </div>
                                <button
                                    onClick={() => setIsAddingNew(true)}
                                    className={`px-6 py-3 rounded-xl flex items-center gap-2 font-medium transition-all border ${theme === 'dark'
                                            ? 'bg-brand-primary border-brand-primary text-white hover:bg-brand-primary/90'
                                            : 'bg-brand-primary border-brand-primary text-white hover:bg-brand-primary/90 shadow-md hover:shadow-lg'
                                        }`}
                                >
                                    <Plus size={18} />
                                    新增詞彙
                                </button>
                            </div>

                            {/* Add new form */}
                            {isAddingNew && (
                                <div className="p-6 rounded-xl bg-gradient-to-br from-brand-primary/10 to-transparent border border-brand-primary/20 space-y-4 shrink-0 animate-in slide-in-from-top-4 duration-300">
                                    <h3 className="font-medium text-brand-primary flex items-center gap-2">
                                        <Plus size={16} /> 新增詞彙
                                    </h3>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <input
                                            type="text"
                                            value={newEntry.word}
                                            onChange={(e) => setNewEntry({ ...newEntry, word: e.target.value })}
                                            placeholder="詞彙 *"
                                            className={`glass-input ${theme === 'dark' ? '' : 'bg-white border-slate-200 text-slate-800'}`}
                                            autoFocus
                                        />
                                        <select
                                            value={newEntry.category}
                                            onChange={(e) => setNewEntry({ ...newEntry, category: e.target.value })}
                                            className={`glass-input ${theme === 'dark' ? '' : 'bg-white border-slate-200 text-slate-800'}`}
                                        >
                                            {categories.map(cat => (
                                                <option key={cat.name} value={cat.name}>{cat.name}</option>
                                            ))}
                                        </select>
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <input
                                            type="text"
                                            value={newEntry.annotation}
                                            onChange={(e) => setNewEntry({ ...newEntry, annotation: e.target.value })}
                                            placeholder="註解說明"
                                            className={`glass-input w-full ${theme === 'dark' ? '' : 'bg-white border-slate-200 text-slate-800'}`}
                                        />
                                        <input
                                            type="text"
                                            value={newEntry.aliases}
                                            onChange={(e) => setNewEntry({ ...newEntry, aliases: e.target.value })}
                                            placeholder="別名（用逗號分隔）"
                                            className={`glass-input w-full ${theme === 'dark' ? '' : 'bg-white border-slate-200 text-slate-800'}`}
                                        />
                                    </div>
                                    <div className="flex gap-3 justify-end pt-2">
                                        <button


                                            onClick={() => {
                                                setIsAddingNew(false);
                                                setNewEntry({ word: '', annotation: '', aliases: '', category: 'custom' });
                                            }}
                                            className={`px-6 py-2 rounded-lg font-medium transition-colors border ${theme === 'dark'
                                                ? 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white'
                                                : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50 hover:text-slate-900 shadow-sm'
                                                }`}
                                        >
                                            取消
                                        </button>
                                        <button
                                            onClick={handleAddEntry}
                                            disabled={!newEntry.word.trim() || actionLoading === 'add'}
                                            className="px-6 py-2 rounded-lg font-medium bg-emerald-500 border border-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-sm"
                                        >
                                            {actionLoading === 'add' ? (
                                                <Loader2 size={18} className="animate-spin" />
                                            ) : (
                                                <Check size={18} />
                                            )}
                                            確認添加
                                        </button>
                                    </div>
                                </div>
                            )}

                            {/* Entries list */}
                            <div className="flex-1 overflow-y-auto pr-2 space-y-3 pb-4">
                                {filteredEntries.map(entry => (
                                    <div
                                        key={entry.word}
                                        className={`p-4 rounded-xl border transition-colors group ${theme === 'dark'
                                            ? 'bg-white/5 border-white/10 hover:bg-white/10'
                                            : 'bg-white border-slate-200 hover:border-brand-primary/50 shadow-sm'
                                            }`}
                                    >
                                        {editingWord === entry.word ? (
                                            /* Edit mode */
                                            <div className="space-y-4">
                                                <div className="flex items-center gap-2 mb-2">
                                                    <span className="font-medium text-white text-lg">{entry.word}</span>
                                                    <span className="text-xs px-2.5 py-1 rounded-full bg-brand-primary/20 text-brand-primary border border-brand-primary/20">
                                                        {entry.category}
                                                    </span>
                                                </div>
                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                    <input
                                                        type="text"
                                                        value={editForm.annotation}
                                                        onChange={(e) => setEditForm({ ...editForm, annotation: e.target.value })}
                                                        placeholder="註解說明"
                                                        className={`glass-input w-full ${theme === 'dark' ? '' : 'bg-white border-slate-200 text-slate-800'}`}
                                                    />
                                                    <input
                                                        type="text"
                                                        value={editForm.aliases}
                                                        onChange={(e) => setEditForm({ ...editForm, aliases: e.target.value })}
                                                        placeholder="別名（用逗號分隔）"
                                                        className={`glass-input w-full ${theme === 'dark' ? '' : 'bg-white border-slate-200 text-slate-800'}`}
                                                    />
                                                </div>
                                                <div className="flex gap-2 justify-end">
                                                    <button
                                                        onClick={() => setEditingWord(null)}
                                                        className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors border ${theme === 'dark'
                                                            ? 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white'
                                                            : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50 hover:text-slate-900 shadow-sm'
                                                            }`}
                                                    >
                                                        取消
                                                    </button>
                                                    <button
                                                        onClick={() => handleSaveEdit(entry.word)}
                                                        disabled={actionLoading === `edit-${entry.word}`}
                                                        className="px-3 py-1.5 rounded-lg text-sm font-medium bg-emerald-500 border border-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-50 flex items-center gap-2 shadow-sm"
                                                    >
                                                        {actionLoading === `edit-${entry.word}` ? (
                                                            <Loader2 size={16} className="animate-spin" />
                                                        ) : (
                                                            <Save size={16} />
                                                        )}
                                                        儲存
                                                    </button>
                                                </div>
                                            </div>
                                        ) : (
                                            /* View mode */
                                            <div className="flex items-center gap-4">
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-3 flex-wrap mb-1">
                                                        <span className={`font-semibold text-lg ${theme === 'dark' ? 'text-white' : 'text-slate-800'
                                                            }`}>{entry.word}</span>
                                                        <span className="text-xs px-2.5 py-1 rounded-full bg-brand-primary/20 text-brand-primary border border-brand-primary/20">
                                                            {entry.category}
                                                        </span>
                                                        {!entry.category_enabled && (
                                                            <span className="text-xs px-2.5 py-1 rounded-full bg-slate-500/20 text-slate-300 border border-slate-500/20">
                                                                類別已停用
                                                            </span>
                                                        )}
                                                    </div>
                                                    {entry.annotation && (
                                                        <p className={`text-base mt-1 ${theme === 'dark' ? 'text-slate-300' : 'text-slate-600'
                                                            }`}>{entry.annotation}</p>
                                                    )}
                                                    {entry.aliases?.length > 0 && (
                                                        <div className="flex items-center gap-2 mt-2">
                                                            <span className="text-xs uppercase tracking-wider text-slate-400">別名</span>
                                                            <p className="text-sm text-slate-300 font-mono bg-black/20 px-2 py-0.5 rounded">{entry.aliases.join(', ')}</p>
                                                        </div>
                                                    )}
                                                </div>
                                                <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                                    <button
                                                        onClick={() => handleStartEdit(entry)}
                                                        className="p-2.5 rounded-lg text-slate-300 hover:text-brand-primary hover:bg-brand-primary/10 transition-all"
                                                        title="編輯"
                                                    >
                                                        <Edit2 size={18} />
                                                    </button>
                                                    <button
                                                        onClick={() => handleDeleteEntry(entry.word)}
                                                        disabled={actionLoading === `delete-${entry.word}`}
                                                        className="p-2.5 rounded-lg text-slate-300 hover:text-red-400 hover:bg-red-500/10 transition-all"
                                                        title="刪除"
                                                    >
                                                        {actionLoading === `delete-${entry.word}` ? (
                                                            <Loader2 size={18} className="animate-spin" />
                                                        ) : (
                                                            <Trash2 size={18} />
                                                        )}
                                                    </button>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ))}

                                {filteredEntries.length === 0 && (
                                    <div className={`flex flex-col items-center justify-center py-16 border-2 border-dashed rounded-xl ${theme === 'dark' ? 'text-slate-400 border-white/5' : 'text-slate-400 border-slate-200'
                                        }`}>
                                        <Search size={48} className="mb-4 opacity-50" />
                                        <p className="text-lg font-medium">沒有找到符合的詞彙</p>
                                        <p className="text-sm opacity-70">試試其他關鍵字或新增一個詞彙</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    ) : (
                        /* Categories tab */
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 overflow-y-auto h-full pr-2 pb-4">
                            {categories.map(category => (
                                <div
                                    key={category.name}
                                    className={`p-6 rounded-xl border transition-all duration-300 ${category.enabled
                                        ? theme === 'dark'
                                            ? 'bg-white/5 border-white/10 hover:border-brand-primary/30'
                                            : 'bg-white border-slate-200 hover:border-brand-primary/50 shadow-sm'
                                        : 'bg-black/20 border-white/5 opacity-75 grayscale-[0.5]'
                                        }`}
                                >
                                    <div className="flex items-start justify-between mb-4">
                                        <div>
                                            <div className="flex items-center gap-3 mb-2">
                                                <span className={`text-xl font-bold ${theme === 'dark' ? 'text-white' : 'text-slate-800'
                                                    }`}>{category.name}</span>
                                                <span className={`text-xs px-2.5 py-1 rounded-full border ${category.priority === 'highest' ? 'bg-red-500/20 text-red-400 border-red-500/20' :
                                                    category.priority === 'high' ? 'bg-orange-500/20 text-orange-400 border-orange-500/20' :
                                                        'bg-slate-500/20 text-slate-300 border-slate-500/20'
                                                    }`}>
                                                    {category.priority}
                                                </span>
                                            </div>
                                            <div className="text-sm text-slate-300 font-mono bg-black/20 px-3 py-1 rounded inline-block">
                                                {category.term_count} 個詞彙
                                            </div>
                                        </div>
                                        <button
                                            onClick={() => handleToggleCategory(category.name)}
                                            disabled={actionLoading === `toggle-${category.name}`}
                                            className={`p-3 rounded-xl transition-all shadow-lg ${category.enabled
                                                ? 'bg-gradient-to-br from-emerald-500/20 to-emerald-500/5 text-emerald-400 border border-emerald-500/20 hover:from-emerald-500/30'
                                                : 'bg-white/5 text-slate-300 border border-white/10 hover:bg-white/10'
                                                }`}
                                        >
                                            {actionLoading === `toggle-${category.name}` ? (
                                                <Loader2 size={24} className="animate-spin" />
                                            ) : category.enabled ? (
                                                <ToggleRight size={28} />
                                            ) : (
                                                <ToggleLeft size={28} />
                                            )}
                                        </button>
                                    </div>

                                    {category.description && (
                                        <div className="pt-4 border-t border-white/5 mt-2">
                                            <p className="text-sm text-slate-300 leading-relaxed">{category.description}</p>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default HotWordsPage;
