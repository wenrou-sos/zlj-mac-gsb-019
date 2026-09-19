import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 10000 })

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const detail = error.response?.data?.detail || error.message
    return Promise.reject(new Error(detail))
  }
)

export default {
  health: () => api.get('/health').then((r) => r.data),
  dashboard: () => api.get('/dashboard').then((r) => r.data),

  docks: () => api.get('/docks').then((r) => r.data),
  createDock: (d) => api.post('/docks', d).then((r) => r.data),

  teams: () => api.get('/teams').then((r) => r.data),
  createTeam: (d) => api.post('/teams', d).then((r) => r.data),
  teamSchedule: (id) => api.get(`/teams/${id}/schedule`).then((r) => r.data),

  projects: () => api.get('/projects').then((r) => r.data),
  project: (id) => api.get(`/projects/${id}`).then((r) => r.data),
  createProject: (d) => api.post('/projects', d).then((r) => r.data),
  updateProject: (id, d) => api.put(`/projects/${id}`, d).then((r) => r.data),

  createTask: (pid, d) => api.post(`/projects/${pid}/tasks`, d).then((r) => r.data),
  updateTask: (pid, tid, d) => api.put(`/projects/${pid}/tasks/${tid}`, d).then((r) => r.data),
  deleteTask: (pid, tid) => api.delete(`/projects/${pid}/tasks/${tid}`),
  addDependency: (pid, tid, depends_on_id) =>
    api.post(`/projects/${pid}/tasks/${tid}/dependencies`, { depends_on_id }).then((r) => r.data),
  assignTeam: (pid, tid, team_id) =>
    api.post(`/projects/${pid}/tasks/${tid}/assignments`, { team_id }).then((r) => r.data),
  unassignTeam: (pid, tid, aid) =>
    api.delete(`/projects/${pid}/tasks/${tid}/assignments/${aid}`),

  parts: (pid) => api.get(`/projects/${pid}/parts`).then((r) => r.data),
  createPart: (pid, d) => api.post(`/projects/${pid}/parts`, d).then((r) => r.data),
  updatePart: (id, d) => api.put(`/parts/${id}`, d).then((r) => r.data),

  occupancies: (pid) => api.get(`/projects/${pid}/occupancies`).then((r) => r.data),
  createOccupancy: (pid, d) => api.post(`/projects/${pid}/occupancies`, d).then((r) => r.data),
  conflicts: (pid) => api.get(`/projects/${pid}/conflicts`).then((r) => r.data),
  recalc: (pid) => api.post(`/projects/${pid}/recalc`).then((r) => r.data)
}
