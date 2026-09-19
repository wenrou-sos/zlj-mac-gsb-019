import axios from 'axios'

const api = axios.create({ baseURL: '/' })

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const detail = error.response?.data?.detail
    if (detail) {
      alert(typeof detail === 'string' ? detail : JSON.stringify(detail))
    }
    return Promise.reject(error)
  },
)

export default {
  // dashboard
  getDashboard: () => api.get('/api/dashboard').then((r) => r.data),
  getLogs: (limit = 50) => api.get('/api/logs', { params: { limit } }).then((r) => r.data),

  // projects & tasks
  listProjects: () => api.get('/api/projects').then((r) => r.data),
  createProject: (data) => api.post('/api/projects', data).then((r) => r.data),
  updateProject: (id, data) => api.patch(`/api/projects/${id}`, data).then((r) => r.data),
  deleteProject: (id) => api.delete(`/api/projects/${id}`),
  listTasks: (projectId) =>
    api.get('/api/tasks', { params: projectId ? { project_id: projectId } : {} }).then((r) => r.data),
  createTask: (data) => api.post('/api/tasks', data).then((r) => r.data),
  updateTask: (id, data) => api.patch(`/api/tasks/${id}`, data).then((r) => r.data),
  deleteTask: (id) => api.delete(`/api/tasks/${id}`),
  reportDelay: (id, days) => api.post(`/api/tasks/${id}/delay`, { days }).then((r) => r.data),

  // teams
  listTeams: () => api.get('/api/teams').then((r) => r.data),
  createTeam: (data) => api.post('/api/teams', data).then((r) => r.data),
  deleteTeam: (id) => api.delete(`/api/teams/${id}`),
  assignTeam: (taskId, teamId) =>
    api.post('/api/teams/assign', null, { params: { task_id: taskId, team_id: teamId } }).then((r) => r.data),

  // parts
  listParts: () => api.get('/api/parts').then((r) => r.data),
  createPart: (data) => api.post('/api/parts', data).then((r) => r.data),
  updatePart: (id, data) => api.patch(`/api/parts/${id}`, data).then((r) => r.data),
  deletePart: (id) => api.delete(`/api/parts/${id}`),

  // docks & bookings
  listDocks: () => api.get('/api/docks').then((r) => r.data),
  createDock: (data) => api.post('/api/docks', data).then((r) => r.data),
  deleteDock: (id) => api.delete(`/api/docks/${id}`),
  listBookings: () => api.get('/api/docks/bookings').then((r) => r.data),
  createBooking: (data) => api.post('/api/docks/bookings', data).then((r) => r.data),
  deleteBooking: (id) => api.delete(`/api/docks/bookings/${id}`),
}
