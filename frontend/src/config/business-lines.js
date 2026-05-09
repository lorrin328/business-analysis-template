export const BUSINESS_LINES = [
  {
    code: 'jingdai',
    name: '经代',
    displayName: '经代',
    color: '#8b5cf6',
    order: 10,
    isIncludedInTotal: true,
    supportOrgDimension: false,
    supportTeamDimension: false,
    supportDailyTrend: true
  },
  {
    code: 'oto',
    name: 'OTO',
    displayName: 'OTO',
    color: '#3b82f6',
    order: 20,
    isIncludedInTotal: true,
    supportOrgDimension: true,
    supportTeamDimension: true,
    supportDailyTrend: true
  },
  {
    code: 'zhengbao',
    name: '证保',
    displayName: '证保',
    color: '#10b981',
    order: 30,
    isIncludedInTotal: true,
    supportOrgDimension: true,
    supportTeamDimension: true,
    supportDailyTrend: true
  },
  {
    code: 'yiqiao',
    name: '蚁桥',
    displayName: '蚁桥',
    color: '#f59e0b',
    order: 40,
    isIncludedInTotal: true,
    supportOrgDimension: true,
    supportTeamDimension: true,
    supportDailyTrend: true
  },
  {
    code: 'transform',
    name: '转型业务',
    displayName: '转型业务',
    color: '#14b8a6',
    order: 50,
    isIncludedInTotal: true,
    supportOrgDimension: true,
    supportTeamDimension: true,
    supportDailyTrend: true
  },
  {
    code: 'total',
    name: '整体业务',
    displayName: '整体业务',
    color: '#e2e8f0',
    order: 60,
    isIncludedInTotal: false,
    supportOrgDimension: false,
    supportTeamDimension: false,
    supportDailyTrend: true
  }
];

export function getBusinessLine(name) {
  return BUSINESS_LINES.find(item => item.name === name || item.displayName === name || item.code === name);
}

export function supportsOrgDimension(name) {
  const line = getBusinessLine(name);
  return Boolean(line && line.supportOrgDimension);
}
