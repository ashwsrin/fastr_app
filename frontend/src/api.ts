const API_BASE_URL = 'http://127.0.0.1:8000/api';

export type ChatMessage = {
    role: 'user' | 'assistant';
    content: string;
};

export type ChatResponse = {
    type: 'chat' | 'table_discovery' | 'sql_generation';
    content: string;
    sql?: string;
};

export const api = {
    /**
     * Send a message to the AI agent, including conversation history.
     */
    async sendMessage(prompt: string, history: ChatMessage[] = []): Promise<ChatResponse> {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ prompt, history }),
        });

        if (!response.ok) {
            throw new Error(`Chat API error: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * Directly trigger discovery without the agent.
     */
    async discoverTables(query: string, pillar?: string, module?: string) {
        const params = new URLSearchParams({ query });
        if (pillar) params.append('pillar', pillar);
        if (module) params.append('module', module);

        const response = await fetch(`${API_BASE_URL}/discover?${params.toString()}`);
        if (!response.ok) {
            throw new Error(`Discovery API error: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * Directly fetch table metadata without the agent.
     */
    async getTableMetadata(tableName: string) {
        const response = await fetch(`${API_BASE_URL}/metadata/${tableName}`);
        if (!response.ok) {
            throw new Error(`Metadata API error: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * Get all Fusion Instances
     */
    async getInstances() {
        const response = await fetch(`${API_BASE_URL}/instances`);
        if (!response.ok) {
            throw new Error(`Instances API error: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * Create Fusion Instance
     */
    async createInstance(payload: any) {
        const response = await fetch(`${API_BASE_URL}/instances`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || `Failed to create instance: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * Update Fusion Instance
     */
    async updateInstance(envId: number, payload: any) {
        const response = await fetch(`${API_BASE_URL}/instances/${envId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || `Failed to update instance: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * Delete Fusion Instance
     */
    async deleteInstance(envId: number) {
        const response = await fetch(`${API_BASE_URL}/instances/${envId}`, {
            method: 'DELETE'
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || `Failed to delete instance: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * Execute SQL Query
     */
    async executeQuery(query: string, instanceId: number, password: string, limit: number) {
        const response = await fetch(`${API_BASE_URL}/execute`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query,
                instance_id: instanceId,
                password,
                limit
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw errorData;
        }
        return response.json();
    },

    /**
     * Create BI Report (if missing)
     */
    async createReport(instanceId: number, password: string) {
        const response = await fetch(`${API_BASE_URL}/execute/create-report`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                instance_id: instanceId,
                password
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw errorData;
        }
        return response.json();
    },

    /**
     * Get SQL Execution History
     */
    async getHistory() {
        const response = await fetch(`${API_BASE_URL}/history`);
        if (!response.ok) {
            throw new Error(`History API error: ${response.statusText}`);
        }
        return response.json();
    }
};
