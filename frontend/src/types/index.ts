export interface Client {
  id: string
  name: string
  email: string
  phone: string
  address: string
  tax_id?: string
  vekalet_ofis_no?: string
  created_at: string
  updated_at: string
  version: number
}

export interface ClientCreate {
  name: string
  email: string
  phone: string
  address: string
  tax_id?: string
  vekalet_ofis_no?: string
}

export interface ClientUpdate {
  name?: string
  email?: string
  phone?: string
  address?: string
  tax_id?: string
  vekalet_ofis_no?: string
  version: number}