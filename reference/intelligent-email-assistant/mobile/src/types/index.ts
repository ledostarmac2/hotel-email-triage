// API Response Types
export interface DashboardStats {
  totalEmails: number;
  urgentEmails: number;
  autoResponses: number;
  processedToday: number;
}

export interface Email {
  id: string;
  subject: string;
  sender: string;
  receivedAt: string;
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
  processed: boolean;
  requiresAttention: boolean;
  category: 'WORK' | 'MEETING' | 'NEWSLETTER' | 'OTHER';
  summary: string;
  content?: string;
}

export interface EmailResponse {
  content: Email[];
  totalElements: number;
  totalPages: number;
  first: boolean;
  last: boolean;
}

export interface Notification {
  id: string;
  type: 'urgent' | 'auto_response' | 'processing' | 'whatsapp' | 'error';
  title: string;
  message: string;
  time: string;
  read: boolean;
  icon?: string;
  color?: string;
}

export interface UserSettings {
  pushNotifications: boolean;
  whatsappNotifications: boolean;
  autoResponses: boolean;
  processingSchedule: string;
  aiProvider: string;
}

export interface ProcessingResult {
  success: boolean;
  message: string;
  processedCount: number;
}

// Redux State Types
export interface DashboardState {
  stats: DashboardStats;
  loading: boolean;
  error: string | null;
  processingInProgress: boolean;
  lastProcessingResult: ProcessingResult | null;
}

export interface EmailsState {
  emails: Email[];
  selectedEmail: Email | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  pagination: {
    currentPage: number;
    totalPages: number;
    totalElements: number;
    hasMore: boolean;
  };
}

export interface NotificationsState {
  notifications: Notification[];
  loading: boolean;
  error: string | null;
  unreadCount: number;
}

export interface SettingsState {
  settings: UserSettings;
  loading: boolean;
  saving: boolean;
  error: string | null;
}

export interface RootState {
  dashboard: DashboardState;
  emails: EmailsState;
  notifications: NotificationsState;
  settings: SettingsState;
}

// Component Props Types
export interface ScreenProps {
  navigation: any; // TODO: Replace with proper navigation types
}

// API Service Types
export interface ApiError {
  message: string;
  status?: number;
}

export interface ApiResponse<T> {
  success?: boolean;
  data?: T;
  settings?: T; // For backwards compatibility
  error?: ApiError;
}

// Async Thunk Types
export interface AsyncThunkConfig {
  state: RootState;
  rejectValue: ApiError;
}

// Test Utility Types
export interface MockStoreState {
  dashboard?: Partial<DashboardState>;
  emails?: Partial<EmailsState>;
  notifications?: Partial<NotificationsState>;
  settings?: Partial<SettingsState>;
}
