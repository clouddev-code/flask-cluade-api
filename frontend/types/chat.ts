/**
 * メッセージの役割
 */
export type MessageRole = 'user' | 'assistant';

/**
 * チャットメッセージ
 */
export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
}

/**
 * SSEレスポンスのデータ型
 */
export interface SSEData {
  chunk?: string;
  text?: string;
  done?: boolean;
  error?: string;
}

/**
 * チャット状態
 */
export interface ChatState {
  messages: Message[];
  isLoading: boolean;
  error: string | null;
}
