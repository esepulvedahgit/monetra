import Svg, { Circle, Path, Rect } from 'react-native-svg';

export type IconName = 'grid' | 'arrows' | 'target' | 'user' | 'plus' | 'chevron-left' | 'chevron-right' | 'income' | 'expense' | 'calendar' | 'edit' | 'trash' | 'close' | 'wallet' | 'eye' | 'eye-off' | 'lock';

export function Icon({ name, size = 20, color = '#31302e', strokeWidth = 1.8 }: { name: IconName; size?: number; color?: string; strokeWidth?: number }) {
  const props = { stroke: color, strokeWidth, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, fill: 'none' };
  const content = {
    grid: <><Rect x="4" y="4" width="6" height="6" rx="1" {...props} /><Rect x="14" y="4" width="6" height="6" rx="1" {...props} /><Rect x="4" y="14" width="6" height="6" rx="1" {...props} /><Rect x="14" y="14" width="6" height="6" rx="1" {...props} /></>,
    arrows: <><Path d="M7 4v16m0 0-3-3m3 3 3-3M17 20V4m0 0-3 3m3-3 3 3" {...props} /></>,
    target: <><Circle cx="12" cy="12" r="8" {...props} /><Circle cx="12" cy="12" r="4" {...props} /><Path d="m18 6 2-2" {...props} /></>,
    user: <><Circle cx="12" cy="8" r="3" {...props} /><Path d="M5 20c.8-3.2 3-5 7-5s6.2 1.8 7 5" {...props} /></>,
    plus: <Path d="M12 5v14M5 12h14" {...props} />,
    'chevron-left': <Path d="m15 18-6-6 6-6" {...props} />,
    'chevron-right': <Path d="m9 18 6-6-6-6" {...props} />,
    income: <Path d="M12 19V5m-5 5 5-5 5 5" {...props} />,
    expense: <Path d="M12 5v14m5-5-5 5-5-5" {...props} />,
    calendar: <><Rect x="4" y="5" width="16" height="15" rx="2" {...props} /><Path d="M8 3v4m8-4v4M4 10h16" {...props} /></>,
    edit: <><Path d="m14.5 5.5 4 4M4 20l4.2-1 10.6-10.6a2.8 2.8 0 0 0-4-4L4.2 15z" {...props} /></>,
    trash: <><Path d="M4 7h16M10 11v5m4-5v5M9 7l1-3h4l1 3M6 7l1 13h10l1-13" {...props} /></>,
    close: <Path d="m6 6 12 12M18 6 6 18" {...props} />,
    lock: <><Rect x="5" y="10" width="14" height="10" rx="2" {...props} /><Path d="M8 10V7a4 4 0 0 1 8 0v3" {...props} /><Circle cx="12" cy="15" r="1" fill={color} /></>,
    eye: <><Path d="M3.5 12s3-5 8.5-5 8.5 5 8.5 5-3 5-8.5 5-8.5-5-8.5-5Z" {...props} /><Circle cx="12" cy="12" r="2.5" {...props} /></>,
    'eye-off': <><Path d="m4 4 16 16M10.6 6.3A9.8 9.8 0 0 1 12 6c5.5 0 8.5 6 8.5 6a16.8 16.8 0 0 1-3.1 3.7M6.2 8.1A16 16 0 0 0 3.5 12S6.5 18 12 18c.7 0 1.4-.1 2-.3" {...props} /><Path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" {...props} /></>,
    wallet: <><Path d="M4 7a3 3 0 0 1 3-3h10v16H7a3 3 0 0 1-3-3z" {...props} /><Path d="M17 9h3v6h-3a3 3 0 0 1 0-6Z" {...props} /><Circle cx="17" cy="12" r=".7" fill={color} /></>,
  }[name];
  return <Svg width={size} height={size} viewBox="0 0 24 24">{content}</Svg>;
}
