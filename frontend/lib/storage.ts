import { Message } from '@/types/chat';

const STORAGE_KEY = 'chat_messages';

/**
 * LocalStorageにメッセージを保存
 */
export function saveMessages(messages: Message[]): void {
  if (typeof window === 'undefined') return;

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
  } catch (error) {
    console.error('Failed to save messages to localStorage:', error);
  }
}

/**
 * LocalStorageからメッセージを読み込み
 */
export function loadMessages(): Message[] {
  if (typeof window === 'undefined') return [];

  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return [];

    const messages = JSON.parse(stored);
    return Array.isArray(messages) ? messages : [];
  } catch (error) {
    console.error('Failed to load messages from localStorage:', error);
    return [];
  }
}

/**
 * LocalStorageのメッセージをクリア
 */
export function clearMessages(): void {
  if (typeof window === 'undefined') return;

  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (error) {
    console.error('Failed to clear messages from localStorage:', error);
  }
}
