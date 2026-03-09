import { useState, useRef, useEffect } from 'react'
import { api, type ChatMessage } from '../api'
import CodeMirror from '@uiw/react-codemirror'
import { sql } from '@codemirror/lang-sql'
import Split from 'react-split'
import DataTable from 'react-data-table-component'
import Papa from 'papaparse'
import { format } from 'sql-formatter'

type Message = {
    id: string
    role: 'user' | 'assistant'
    content: string
    type: 'chat' | 'sql_generation' | 'table_discovery'
    sql?: string
}

type Instance = {
    ENV_ID: number;
    ENV_NAME: string;
    FUSION_USER_NAME: string;
    HOST: string;
    DEFAULT_INSTANCE: string;
}

export default function SqlDeveloper() {
    const [messages, setMessages] = useState<Message[]>([
        {
            id: '1',
            role: 'assistant',
            content: 'Welcome to the Developer view. You can write your SQL queries here and run them against a Fusion instance.',
            type: 'chat'
        }
    ])
    const [inputVal, setInputVal] = useState('')
    const [currentSql, setCurrentSql] = useState('SELECT * FROM FND_LOOKUPS\n')
    const [selectedSql, setSelectedSql] = useState('')
    const [isChatOpen, setIsChatOpen] = useState(false)
    const [isMaximized, setIsMaximized] = useState(false)
    const [isLoading, setIsLoading] = useState(false)

    const [instances, setInstances] = useState<Instance[]>([])
    const [selectedInstanceId, setSelectedInstanceId] = useState<number | null>(null)

    // Cache passwords per instance ID for the session
    const [instancePasswords, setInstancePasswords] = useState<Record<number, string>>({})
    const [showPasswordDialog, setShowPasswordDialog] = useState(false)
    const [passwordInput, setPasswordInput] = useState('')

    const [limit, setLimit] = useState(50)

    // Execution states
    const [isExecuting, setIsExecuting] = useState(false)
    const [errorMsg, setErrorMsg] = useState<string | null>(null)
    const [showCreateReportPrompt, setShowCreateReportPrompt] = useState(false)

    // Results
    const [columns, setColumns] = useState<any[]>([])
    const [data, setData] = useState<any[]>([])

    // History
    const [historyData, setHistoryData] = useState<any[]>([])
    const [activeTab, setActiveTab] = useState<'results' | 'history'>('results')

    // Instance Management
    const [showInstanceDialog, setShowInstanceDialog] = useState(false)
    const [editingInstance, setEditingInstance] = useState<Partial<Instance> | null>(null)

    const chatBottomRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        fetchInstances()
        fetchHistory()
    }, [])

    const fetchHistory = async () => {
        try {
            const res = await api.getHistory()
            setHistoryData(res)
        } catch (e) {
            console.error("Failed to load history", e)
        }
    }

    const historyColumns = [
        { name: 'Username', selector: (row: any) => row.USERNAME, sortable: true, wrap: false },
        { name: 'Execution Date', selector: (row: any) => new Date(row.EXECUTION_DATE).toLocaleString(), sortable: true },
        {
            name: 'Append',
            cell: (row: any) => (
                <button
                    className="icon-btn"
                    style={{ padding: '8px', color: 'var(--accent-color)' }}
                    onClick={() => setCurrentSql(prev => prev + '\n' + row.QUERY)}
                    title="Append query to editor"
                >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 20v-8m0 0V4m0 8h8m-8 0H4" /></svg>
                </button>
            ),
            width: '80px',
            center: true
        },
        {
            name: 'Replace',
            cell: (row: any) => (
                <button
                    className="icon-btn"
                    style={{ padding: '8px', color: 'var(--accent-color)' }}
                    onClick={() => setCurrentSql(row.QUERY)}
                    title="Replace query in editor"
                >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                </button>
            ),
            width: '80px',
            center: true
        },
        { name: 'Query', selector: (row: any) => row.QUERY, sortable: true, wrap: true, grow: 3 }
    ];

    const fetchInstances = async () => {
        try {
            const res = await api.getInstances();
            setInstances(res);
            if (res.length > 0) {
                const defaultInst = res.find((i: Instance) => i.DEFAULT_INSTANCE === 'Y')
                if (defaultInst) {
                    setSelectedInstanceId(defaultInst.ENV_ID)
                } else {
                    setSelectedInstanceId(res[0].ENV_ID)
                }
            }
        } catch (e) {
            console.error("Failed to load instances", e)
        }
    }

    const handleCopy = (text: string) => {
        navigator.clipboard.writeText(text);
    }

    // Scroll chat to bottom when new messages arrive
    useEffect(() => {
        if (isChatOpen && chatBottomRef.current) {
            chatBottomRef.current.scrollIntoView({ behavior: 'smooth' })
        }
    }, [messages, isChatOpen, isLoading])

    const handleSend = async () => {
        if (!inputVal.trim() || isLoading) return

        const userPrompt = inputVal;

        // Add user message to UI
        const userMsg: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: userPrompt,
            type: 'chat'
        }

        setMessages(prev => [...prev, userMsg])
        setInputVal('')
        setIsLoading(true)

        try {
            // Format history for the API (only needs role and content)
            const history: ChatMessage[] = messages.map(m => ({
                role: m.role,
                content: m.content
            }));

            // Call the real agentic backend
            const response = await api.sendMessage(userPrompt, history);

            const aiMsg: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: response.content,
                type: response.type,
                sql: response.sql
            }

            setMessages(prev => [...prev, aiMsg])

            if (response.type === 'sql_generation' && response.sql) {
                setCurrentSql(response.sql + '\n')
            }
        } catch (error) {
            console.error("Error communicating with FASTR backend:", error);
            setMessages(prev => [...prev, {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: 'Sorry, I encountered an error.',
                type: 'chat'
            }])
        } finally {
            setIsLoading(false)
        }
    }

    const handleExecuteClick = () => {
        if (!selectedInstanceId) {
            setErrorMsg("Please select an instance first.");
            return;
        }
        const queryToRun = selectedSql.trim() ? selectedSql : currentSql;
        if (!queryToRun.trim()) {
            setErrorMsg("Please enter a SQL query.");
            return;
        }

        setErrorMsg(null);

        const cachedPwd = instancePasswords[selectedInstanceId];
        if (!cachedPwd) {
            setShowPasswordDialog(true);
        } else {
            runExecution(cachedPwd);
        }
    }

    const handleSubmitPassword = () => {
        if (!selectedInstanceId) return;
        setInstancePasswords(prev => ({ ...prev, [selectedInstanceId]: passwordInput }));
        setShowPasswordDialog(false);
        runExecution(passwordInput);
        setPasswordInput('');
    }

    const runExecution = async (pwd: string) => {
        setIsExecuting(true);
        setErrorMsg(null);
        setShowCreateReportPrompt(false);
        setColumns([]);
        setData([]);

        try {
            if (!selectedInstanceId) return;
            const queryToRun = selectedSql.trim() ? selectedSql : currentSql;
            const result = await api.executeQuery(queryToRun, selectedInstanceId, pwd, limit);

            if (result.columns && result.rows) {
                const dataTableCols = result.columns.map((c: string) => ({
                    name: c,
                    selector: (row: any) => row[c],
                    sortable: true,
                    reorder: true
                }));

                const dataTableRows = result.rows.map((rowArr: any[]) => {
                    const rowObj: any = {};
                    result.columns.forEach((c: string, idx: number) => {
                        rowObj[c] = rowArr[idx];
                    });
                    return rowObj;
                });

                setColumns(dataTableCols);
                setData(dataTableRows);

                // Refresh history after a successful execution
                fetchHistory();
            } else {
                setErrorMsg("Unexpected response format.");
            }

        } catch (err: any) {
            if (err.detail && err.detail.error) {
                setErrorMsg(err.detail.error);
                if (err.detail.needs_create) {
                    setShowCreateReportPrompt(true);
                }
            } else if (err.detail) {
                setErrorMsg(err.detail);
            } else {
                setErrorMsg(err.message || 'Error executing query.');
            }
        } finally {
            setIsExecuting(false);
        }
    }

    const handleCreateReport = async () => {
        setIsExecuting(true);
        setErrorMsg("Creating report objects on Fusion... this may take a moment.");
        try {
            if (!selectedInstanceId) return;
            const pwd = instancePasswords[selectedInstanceId];
            if (!pwd) throw new Error("Missing password for operation.");

            await api.createReport(selectedInstanceId, pwd);
            setErrorMsg(null);
            setShowCreateReportPrompt(false);
            // Auto re-run execution
            runExecution(pwd);
        } catch (err: any) {
            setErrorMsg("Failed to create report: " + (err.detail || err.message));
        } finally {
            setIsExecuting(false);
        }
    }

    const downloadCSV = () => {
        const csv = Papa.unparse(data);
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.setAttribute("href", url);
        link.setAttribute("download", "fastr_export.csv");
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    const handleSaveInstance = async () => {
        if (!editingInstance?.ENV_NAME || !editingInstance?.HOST || !editingInstance?.FUSION_USER_NAME) {
            alert("Please fill in all required fields.");
            return;
        }

        try {
            const payload = {
                env_name: editingInstance.ENV_NAME,
                host: editingInstance.HOST,
                fusion_user_name: editingInstance.FUSION_USER_NAME,
                default_instance: editingInstance.DEFAULT_INSTANCE || 'N'
            };

            if (editingInstance.ENV_ID) {
                await api.updateInstance(editingInstance.ENV_ID, { ...payload, env_id: editingInstance.ENV_ID });
            } else {
                await api.createInstance(payload);
            }

            setEditingInstance(null);
            fetchInstances(); // Refresh list
        } catch (e: any) {
            alert(e.message);
        }
    }

    const handleDeleteInstance = async (id: number) => {
        if (!confirm("Are you sure you want to delete this instance?")) return;
        try {
            await api.deleteInstance(id);
            if (selectedInstanceId === id) setSelectedInstanceId(null);
            fetchInstances();
        } catch (e: any) {
            alert(e.message);
        }
    }

    return (
        <>
            <div className="execute-section flex-col">
                <div className="execute-header">
                    <div className="execute-title">Developer Workspace</div>
                    <div className="execute-actions">
                        <select className="styled-select"
                            value={limit.toString()}
                            onChange={(e) => setLimit(parseInt(e.target.value))}>
                            <option value="50">Limit: 50 Rows</option>
                            <option value="100">Limit: 100 Rows</option>
                            <option value="500">Limit: 500 Rows</option>
                            <option value="1000">Limit: 1000 Rows</option>
                        </select>
                        <select className="styled-select"
                            value={selectedInstanceId?.toString() || ''}
                            onChange={(e) => setSelectedInstanceId(parseInt(e.target.value))}>
                            <option value="">-- Select Instance --</option>
                            {instances.map(inst => (
                                <option key={inst.ENV_ID} value={inst.ENV_ID}>{inst.ENV_NAME} ({inst.FUSION_USER_NAME})</option>
                            ))}
                        </select>
                        <button className="icon-btn" style={{ marginLeft: '-12px', marginRight: '8px' }} onClick={() => setShowInstanceDialog(true)} title="Manage Instances">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                        </button>
                        <button className="btn primary" onClick={handleExecuteClick} disabled={isExecuting}>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                            {isExecuting ? 'Executing...' : 'Execute'}
                        </button>
                    </div>
                </div>

                <div className="developer-area">
                    <Split
                        sizes={[40, 60]}
                        minSize={100}
                        expandToMin={false}
                        gutterSize={10}
                        gutterAlign="center"
                        snapOffset={30}
                        dragInterval={1}
                        direction="vertical"
                        cursor="row-resize"
                        style={{ display: 'flex', flexDirection: 'column', height: '100%' }}
                        className="split-vertical"
                    >
                        <div className="editor-panel flex-col" style={{ overflow: 'hidden' }}>
                            <div className="editor-container" style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden', borderRight: '1px solid var(--panel-border)', borderBottom: '1px solid var(--panel-border)' }}>
                                <div className="editor-toolbar" style={{ padding: '8px 16px', background: '#f8f9fa', borderBottom: '1px solid var(--panel-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                                    <span>SQL Editor</span>
                                    <button
                                        className="icon-btn"
                                        onClick={() => {
                                            try {
                                                const formatted = format(currentSql, { language: 'plsql', tabWidth: 4, keywordCase: 'upper' });
                                                setCurrentSql(formatted);
                                            } catch (e) {
                                                console.error("Format error", e);
                                            }
                                        }}
                                        title="Format SQL"
                                        style={{ fontSize: '0.75rem', padding: '4px 8px', border: '1px solid var(--panel-border)', borderRadius: '4px', background: 'white' }}
                                    >
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '4px', verticalAlign: 'middle' }}><line x1="21" y1="10" x2="3" y2="10"></line><line x1="21" y1="6" x2="3" y2="6"></line><line x1="21" y1="14" x2="3" y2="14"></line><line x1="21" y1="18" x2="3" y2="18"></line></svg>
                                        Format
                                    </button>
                                </div>
                                <div style={{ flex: 1, overflow: 'auto' }}>
                                    <CodeMirror
                                        value={currentSql}
                                        height="100%"
                                        extensions={[sql()]}
                                        onChange={(value) => setCurrentSql(value)}
                                        onUpdate={(viewUpdate) => {
                                            const { state } = viewUpdate;
                                            const selection = state.selection.main;
                                            if (!selection.empty) {
                                                setSelectedSql(state.sliceDoc(selection.from, selection.to));
                                            } else {
                                                setSelectedSql('');
                                            }
                                        }}
                                        theme="light"
                                        style={{ height: '100%', fontSize: '14px' }}
                                    />
                                </div>
                            </div>
                        </div>

                        <div className="results-panel flex-col" style={{ overflow: 'hidden' }}>
                            <div className="results-container" style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#ffffff', overflow: 'hidden' }}>
                                <div className="results-toolbar" style={{ padding: '0', background: '#f8f9fa', borderBottom: '1px solid var(--panel-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <div className="tab-buttons" style={{ display: 'flex' }}>
                                        <button
                                            onClick={() => setActiveTab('results')}
                                            style={{ background: 'none', border: 'none', padding: '12px 24px', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer', borderBottom: activeTab === 'results' ? '2px solid var(--accent-color)' : '2px solid transparent', color: activeTab === 'results' ? 'var(--text-primary)' : 'var(--text-secondary)' }}
                                        >
                                            Results
                                        </button>
                                        <button
                                            onClick={() => setActiveTab('history')}
                                            style={{ background: 'none', border: 'none', padding: '12px 24px', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer', borderBottom: activeTab === 'history' ? '2px solid var(--accent-color)' : '2px solid transparent', color: activeTab === 'history' ? 'var(--text-primary)' : 'var(--text-secondary)' }}
                                        >
                                            History
                                        </button>
                                    </div>
                                    {activeTab === 'results' && data.length > 0 && (
                                        <button className="icon-btn" style={{ fontSize: '0.75rem', padding: '4px 8px', marginRight: '16px' }} onClick={downloadCSV}>
                                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '4px' }}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                                            Export CSV
                                        </button>
                                    )}
                                </div>

                                <div className="results-grid" style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
                                    {activeTab === 'results' ? (
                                        <>
                                            {errorMsg && (
                                                <div className="error-banner" style={{ padding: '16px', background: '#ffebee', color: '#c62828', borderRadius: '8px', marginBottom: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                                    <div style={{ fontWeight: 600 }}>Error executing query</div>
                                                    <div>{errorMsg}</div>
                                                    {showCreateReportPrompt && (
                                                        <div style={{ marginTop: '8px' }}>
                                                            <p style={{ marginBottom: '8px' }}>The FASTR generic report model is not deployed on this instance.</p>
                                                            <button className="btn primary" onClick={handleCreateReport} disabled={isExecuting}>Deploy Report Model Now</button>
                                                        </div>
                                                    )}
                                                </div>
                                            )}

                                            {!errorMsg && data.length === 0 && !isExecuting && (
                                                <div className="empty-state" style={{ marginTop: '40px' }}>
                                                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" style={{ marginBottom: '16px', opacity: 0.3 }}>
                                                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line>
                                                    </svg>
                                                    <h3>No Results</h3>
                                                    <p>Run a query to see data here.</p>
                                                </div>
                                            )}

                                            {isExecuting && !errorMsg && (
                                                <div className="loading-state" style={{ textAlign: 'center', marginTop: '40px', color: 'var(--text-secondary)' }}>
                                                    Executing query...
                                                </div>
                                            )}

                                            {!errorMsg && data.length > 0 && (
                                                <DataTable
                                                    columns={columns}
                                                    data={data}
                                                    pagination
                                                    paginationPerPage={50}
                                                    paginationRowsPerPageOptions={[50, 100, 500]}
                                                    dense
                                                    highlightOnHover
                                                    customStyles={{
                                                        headRow: {
                                                            style: {
                                                                backgroundColor: '#f8f9fa',
                                                                fontWeight: 600,
                                                            }
                                                        }
                                                    }}
                                                />
                                            )}
                                        </>
                                    ) : (
                                        <DataTable
                                            columns={historyColumns}
                                            data={historyData}
                                            pagination
                                            paginationPerPage={15}
                                            highlightOnHover
                                            customStyles={{
                                                headRow: {
                                                    style: {
                                                        backgroundColor: '#f8f9fa',
                                                        fontWeight: 600,
                                                    }
                                                }
                                            }}
                                        />
                                    )}
                                </div>
                            </div>
                        </div>
                    </Split>
                </div>
            </div>

            {/* Password Dialog Modal */}
            {
                showPasswordDialog && (
                    <div className="modal-overlay" style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <div className="modal-content" style={{ background: 'white', padding: '24px', borderRadius: '8px', width: '400px', boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}>
                            <h3 style={{ marginTop: 0, marginBottom: '16px' }}>Provide Password</h3>
                            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                                Enter the password for user <b>{instances.find(i => i.ENV_ID === selectedInstanceId)?.FUSION_USER_NAME}</b>.
                                <br /><i>This is retained for your session and never saved directly to the database.</i>
                            </p>
                            <input
                                type="password"
                                className="chat-input"
                                style={{ width: '100%', marginBottom: '16px', border: '1px solid var(--panel-border)' }}
                                placeholder="Password"
                                value={passwordInput}
                                onChange={e => setPasswordInput(e.target.value)}
                                onKeyDown={e => { if (e.key === 'Enter') handleSubmitPassword() }}
                                autoFocus
                            />
                            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                                <button className="btn" style={{ padding: '8px 16px', background: '#f1f3f4', color: '#333333', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 500 }} onClick={() => setShowPasswordDialog(false)}>Cancel</button>
                                <button className="btn primary" onClick={handleSubmitPassword}>Continue</button>
                            </div>
                        </div>
                    </div>
                )
            }

            {/* Instance Management Dialog Modal */}
            {
                showInstanceDialog && (
                    <div className="modal-overlay" style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <div className="modal-content" style={{ background: 'white', padding: '24px', borderRadius: '8px', width: '600px', maxHeight: '80vh', display: 'flex', flexDirection: 'column', boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                                <h3 style={{ margin: 0 }}>Manage Fusion Instances</h3>
                                <button className="icon-btn" onClick={() => { setShowInstanceDialog(false); setEditingInstance(null); }}>
                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                                </button>
                            </div>

                            {!editingInstance ? (
                                <>
                                    <div style={{ flex: 1, overflow: 'auto', border: '1px solid var(--panel-border)', borderRadius: '4px', marginBottom: '16px' }}>
                                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                                            <thead style={{ background: '#f8f9fa', position: 'sticky', top: 0 }}>
                                                <tr>
                                                    <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid var(--panel-border)' }}>Name</th>
                                                    <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid var(--panel-border)' }}>Host</th>
                                                    <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid var(--panel-border)' }}>Username</th>
                                                    <th style={{ padding: '8px', textAlign: 'center', borderBottom: '1px solid var(--panel-border)', width: '80px' }}>Actions</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {instances.length === 0 ? (
                                                    <tr><td colSpan={4} style={{ padding: '16px', textAlign: 'center', color: 'var(--text-secondary)' }}>No instances found.</td></tr>
                                                ) : instances.map(inst => (
                                                    <tr key={inst.ENV_ID}>
                                                        <td style={{ padding: '8px', borderBottom: '1px solid var(--panel-border)' }}>
                                                            {inst.ENV_NAME} {inst.DEFAULT_INSTANCE === 'Y' && <span style={{ marginLeft: '4px', background: 'var(--accent-color)', color: 'white', padding: '2px 4px', borderRadius: '4px', fontSize: '0.7rem' }}>Default</span>}
                                                        </td>
                                                        <td style={{ padding: '8px', borderBottom: '1px solid var(--panel-border)' }}>{inst.HOST}</td>
                                                        <td style={{ padding: '8px', borderBottom: '1px solid var(--panel-border)' }}>{inst.FUSION_USER_NAME}</td>
                                                        <td style={{ padding: '8px', borderBottom: '1px solid var(--panel-border)', textAlign: 'center' }}>
                                                            <button className="icon-btn" style={{ padding: '4px' }} onClick={() => setEditingInstance(inst)} title="Edit">
                                                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                                                            </button>
                                                            <button className="icon-btn" style={{ padding: '4px', color: '#c62828' }} onClick={() => handleDeleteInstance(inst.ENV_ID)} title="Delete">
                                                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                                                            </button>
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                    <div style={{ display: 'flex', justifySelf: 'flex-end' }}>
                                        <button className="btn primary" onClick={() => setEditingInstance({ DEFAULT_INSTANCE: 'N' })}>
                                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                                            Add Instance
                                        </button>
                                    </div>
                                </>
                            ) : (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                    <div>
                                        <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '4px' }}>Environment Name *</label>
                                        <input type="text" className="chat-input" style={{ width: '100%', border: '1px solid var(--panel-border)' }}
                                            value={editingInstance.ENV_NAME || ''} onChange={e => setEditingInstance({ ...editingInstance, ENV_NAME: e.target.value })} placeholder="e.g. Production, Dev1" />
                                    </div>
                                    <div>
                                        <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '4px' }}>Host URL *</label>
                                        <input type="text" className="chat-input" style={{ width: '100%', border: '1px solid var(--panel-border)' }}
                                            value={editingInstance.HOST || ''} onChange={e => setEditingInstance({ ...editingInstance, HOST: e.target.value })} placeholder="https://....oraclecloud.com" />
                                    </div>
                                    <div>
                                        <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '4px' }}>Fusion Username *</label>
                                        <input type="text" className="chat-input" style={{ width: '100%', border: '1px solid var(--panel-border)' }}
                                            value={editingInstance.FUSION_USER_NAME || ''} onChange={e => setEditingInstance({ ...editingInstance, FUSION_USER_NAME: e.target.value })} placeholder="e.g. admin@oracle.com" />
                                    </div>
                                    <label style={{ display: 'flex', alignItems: 'center', fontSize: '0.85rem', cursor: 'pointer' }}>
                                        <input type="checkbox" checked={editingInstance.DEFAULT_INSTANCE === 'Y'}
                                            onChange={e => setEditingInstance({ ...editingInstance, DEFAULT_INSTANCE: e.target.checked ? 'Y' : 'N' })} style={{ marginRight: '8px' }} />
                                        Set as Default Instance
                                    </label>
                                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
                                        <button className="btn" style={{ padding: '8px 16px', background: '#f1f3f4', color: '#333333', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 500 }} onClick={() => setEditingInstance(null)}>Cancel</button>
                                        <button className="btn primary" onClick={handleSaveInstance}>Save Instance</button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                )
            }

            {/* Floating Chat Widget */}
            {
                !isChatOpen && (
                    <div className="chat-fab-container">
                        <button className="chat-fab" onClick={() => setIsChatOpen(true)}>
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                        </button>
                    </div>
                )
            }

            {/* The Chat Window (conditionally rendered or styled) */}
            <div
                className={`floating-chat-window ${isMaximized ? 'maximized' : ''}`}
                style={{
                    opacity: isChatOpen ? 1 : 0,
                    transform: isChatOpen ? 'scale(1) translateY(0)' : 'scale(0.9) translateY(20px)',
                    pointerEvents: isChatOpen ? 'auto' : 'none'
                }}
            >
                <div className="chat-window-header">
                    <div className="chat-title">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                        Chat Assistant
                    </div>
                    <div className="chat-controls">
                        <button className="chat-header-btn" onClick={() => setIsMaximized(!isMaximized)} title={isMaximized ? "Restore" : "Maximize"}>
                            {isMaximized ? (
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"></path></svg>
                            ) : (
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"></path></svg>
                            )}
                        </button>
                        <button className="chat-header-btn" onClick={() => setIsChatOpen(false)}>
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                        </button>
                    </div>
                </div>

                <div className="chat-container">
                    {messages.map(msg => (
                        <div key={msg.id} className={`message ${msg.role === 'user' ? 'user' : 'ai'}`}>
                            <button className="msg-copy-btn" onClick={() => handleCopy(msg.sql ? msg.content + '\n' + msg.sql : msg.content)} title="Copy to clipboard">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                            </button>
                            {msg.role === 'assistant' && msg.type !== 'chat' && (
                                <div className="message-type">
                                    {msg.type === 'sql_generation' ? '✨ GENERATED SQL' : '🔍 DISCOVERY'}
                                </div>
                            )}

                            <div dangerouslySetInnerHTML={{ __html: msg.content }} />

                            {msg.sql && (
                                <div className="sql-preview-block">
                                    {msg.sql.split('\n')[0]}...
                                </div>
                            )}
                        </div>
                    ))}

                    {isLoading && (
                        <div className="message ai">
                            <div style={{ display: 'flex', gap: '4px', alignItems: 'center', height: '20px' }}>
                                <div className="typing-dot" style={{ animationDelay: '0s' }}>•</div>
                                <div className="typing-dot" style={{ animationDelay: '0.2s' }}>•</div>
                                <div className="typing-dot" style={{ animationDelay: '0.4s' }}>•</div>
                            </div>
                        </div>
                    )}
                    <div ref={chatBottomRef} />
                </div>

                <div className="chat-input-area">
                    <div className="chat-input-wrapper">
                        <textarea
                            className="chat-input"
                            placeholder="Ask about your data..."
                            value={inputVal}
                            onChange={e => setInputVal(e.target.value)}
                            disabled={isLoading}
                            onKeyDown={e => {
                                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
                            }}
                        />
                        <button
                            className="send-btn"
                            onClick={handleSend}
                            disabled={!inputVal.trim() || isLoading}
                        >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <line x1="22" y1="2" x2="11" y2="13"></line>
                                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                            </svg>
                        </button>
                    </div>
                    <div style={{ textAlign: 'center', fontSize: '0.65rem', color: 'var(--text-secondary)', marginTop: '8px' }}>
                        AI can make mistakes. Please check important queries.
                    </div>
                </div>
            </div>
        </>
    )
}
