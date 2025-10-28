'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { Message, SSEData } from '@/types/chat';
import { saveMessages, loadMessages, clearMessages } from '@/lib/storage';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // 初期化時にLocalStorageから履歴を復元
  useEffect(() => {
    const savedMessages = loadMessages();
    if (savedMessages.length > 0) {
      setMessages(savedMessages);
    }
  }, []);

  // メッセージが更新されたらLocalStorageに保存
  useEffect(() => {
    if (messages.length > 0) {
      saveMessages(messages);
    }
  }, [messages]);

  /**
   * メッセージを送信してSSEストリーミングを開始
   */
  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading) return;

    // ユーザーメッセージを追加
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: content.trim(),
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);

    // アシスタントメッセージのプレースホルダーを追加
    const assistantMessageId = `assistant-${Date.now()}`;
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, assistantMessage]);

    try {
      // SSEリクエストを送
      console.log(`Connecting to: ${API_URL}/api/chat/stream`);
      const response = await fetch(`${API_URL}/api/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: {
            text: content.trim(),
          },
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('Response body is not readable');
      }

      // ストリーミングデータを読み取る
      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        // デコードしてSSEデータを解析
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const jsonData = line.substring(6); // "data: " を除去
              const data: SSEData = JSON.parse(jsonData);

              if (data.error) {
                setError(data.error);
                break;
              }

              if (data.text) {
                // アシスタントメッセージを更新
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: data.text || '' }
                      : msg
                  )
                );
              }

              if (data.done) {
                break;
              }
            } catch (parseError) {
              console.error('Failed to parse SSE data:', parseError);
            }
          }
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An error occurred';
      setError(errorMessage);
      console.error('Error sending message:', err);

      // エラーメッセージでアシスタントメッセージを更新
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? { ...msg, content: `エラー: ${errorMessage}` }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  }, [isLoading]);

  /**
   * 会話をクリア
   */
  const clearChat = useCallback(() => {
    setMessages([]);
    clearMessages();
    setError(null);
  }, []);

  /**
   * クリーンアップ
   */
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearChat,
  };
}
