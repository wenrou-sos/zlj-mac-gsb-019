import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Projects from '../views/Projects.vue'
import ProjectDetail from '../views/ProjectDetail.vue'
import Teams from '../views/Teams.vue'
import Docks from '../views/Docks.vue'

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: Dashboard },
    { path: '/projects', component: Projects },
    { path: '/projects/:id', component: ProjectDetail, props: true },
    { path: '/teams', component: Teams },
    { path: '/docks', component: Docks.vue }
  ]
})
