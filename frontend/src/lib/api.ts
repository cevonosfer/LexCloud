const API_URL = (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000'

import type { Client, ClientCreate, ClientUpdate, DashboardData} from '../types'
export type { Client, ClientCreate, ClientUpdate, DashboardData}





export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_URL}${endpoint}`
  const token = localStorage.getItem('auth_token')
  
  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
        ...options.headers,
      },
      ...options,
    })

    if (!response.ok) {
      const errorText = await response.text()
      if (response.status === 401) {
        localStorage.removeItem('auth_token')
        window.location.href = '/login'
      }
      let errorMessage = response.statusText
      try {
        const errorData = JSON.parse(errorText)
        errorMessage = errorData.detail || errorMessage
      } catch {
        errorMessage = errorText || errorMessage
      }
      console.error(`API Error ${response.status}:`, errorMessage)
      throw new ApiError(response.status, errorMessage)
    }

    return response.json()
  } catch (error) {
    console.error('API Request failed:', error)
    if (error instanceof ApiError) {
      throw error
    }
    throw new ApiError(500, 'Network error or server unavailable')
  }
}

export const request = apiRequest

export const api = {
  clients: {
    getAll: (options?: { signal?: AbortSignal }) => apiRequest<Client[]>('/api/clients', options),
    getById: (id: string) => apiRequest<Client>(`/api/clients/${id}`),
    create: (data: ClientCreate) => apiRequest<Client>('/api/clients', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
    update: (id: string, data: ClientUpdate) => apiRequest<Client>(`/api/clients/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
    delete: (id: string) => apiRequest<{ message: string }>(`/api/clients/${id}`, {
      method: 'DELETE',
    }),
  },

  dashboard: {
    getData: () => apiRequest<DashboardData>('/api/dashboard'),
  },
  
  auth: {
    changePassword: (currentPassword: string, newPassword: string) => 
      apiRequest<{ message: string }>('/api/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      }),
  },
  
  backup: {
    export: () => apiRequest<any>('/api/backup'),
    import: (data: any) => apiRequest<{ message: string }>('/api/restore', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  },


 /** cases */

 /** compensation letters */

 /** executions */

}