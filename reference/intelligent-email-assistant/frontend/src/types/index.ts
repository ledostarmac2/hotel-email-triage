export interface EmailEntity {
  id: string;
  emailId: string;
  userId: string;
  subject: string;
  content: string;
  senderEmail: string;
  senderName: string;
  receivedTime: string;
  processedTime?: string;
  requiresAttention: boolean;
  confidenceScore: number;
  category: string;
  sentiment: string;
  llmProvider: string;
  processingStatus: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  whatsappSent: boolean;
  autoResponseSent: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface EmailStats {
  totalProcessed: number;
  requiringAttention: number;
  pendingProcessing: number;
  autoResponded: number;
}

export interface AutoResponseStats {
  totalAutoResponded: number;
  pendingAutoResponse: number;
}

export interface ProcessingStats {
  lastCheckTime: string;
  batchSize: number;
  checkIntervalMinutes: number;
}

export interface UserPreferences {
  userId: string;
  responseStyle: string;
  keywordsRequiringAttention: string[];
  trustedSenders: string[];
  autoRespondSenders: string[];
  enableWhatsAppNotifications: boolean;
  whatsAppNumber: string;
  responseDelayMinutes: number;
  timezone: string;
  workingHours: string[];
  defaultLlmProvider: string;
  confidenceThreshold: number;
}

export interface DashboardData {
  emailStats: EmailStats;
  autoResponseStats: AutoResponseStats;
  processingStats: ProcessingStats;
  recentEmails: EmailEntity[];
}
