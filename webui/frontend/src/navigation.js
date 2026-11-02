export const navigation = [
  { path: '/', label: '总览', icon: 'LayoutDashboard', match: ['/'] },
  { path: '/registered', label: '账户管理', icon: 'Users', match: ['/registered'] },
  { path: '/auto', label: '注册', icon: 'Play', match: ['/auto', '/register'] },
  { id: 'resources', label: '资源', icon: 'Database', children: [
    { path: '/pool', label: '邮箱列表', icon: 'Mail', match: ['/pool', '/import'] },
    { path: '/proxy', label: '代理池', icon: 'Network', match: ['/proxy'] },
  ] },
  { path: '/tasks', label: '任务中心', icon: 'Activity', match: ['/tasks', '/runs'] },
  { path: '/upi', label: 'UPI / Plus', icon: 'ScanSearch', match: ['/upi'] },
  { id: 'settings', label: '设置', icon: 'Settings', children: [
    { path: '/settings/mail', label: '邮箱配置', icon: 'Mail' },
    { path: '/settings/sms', label: '接码配置', icon: 'Smartphone' },
    { path: '/settings/export', label: '自动导出', icon: 'Share2' },
    { path: '/settings/fingerprint', label: '指纹环境', icon: 'Cpu' },
  ] },
]
export const mobileNavigation = [navigation[0], navigation[1], navigation[2], navigation[4]]
export const matchesNavigation = (item, path) => (item.match || [item.path]).includes(path)
