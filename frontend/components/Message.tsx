import { Message as MessageType } from '@/types/chat';

interface MessageProps {
  message: MessageType;
}

export default function Message({ message }: MessageProps) {
  const isUser = message.role === 'user';

  return (
    <div
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4 animate-fadeIn`}
    >
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 ${
          isUser
            ? 'bg-blue-500 text-white'
            : 'bg-gray-100 text-gray-900 dark:bg-gray-700 dark:text-gray-100'
        }`}
      >
        <div className="flex items-start gap-2">
          <div className="flex-shrink-0">
            {isUser ? (
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-sm font-semibold">
                U
              </div>
            ) : (
              <div className="w-8 h-8 rounded-full bg-purple-600 flex items-center justify-center text-sm font-semibold">
                AI
              </div>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium mb-1">
              {isUser ? 'あなた' : 'アシスタント'}
            </div>
            <div className="text-sm whitespace-pre-wrap break-words">
              {message.content || (
                <span className="inline-flex items-center">
                  <svg
                    className="animate-spin h-4 w-4 mr-2"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    ></circle>
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    ></path>
                  </svg>
                  入力中...
                </span>
              )}
            </div>
            <div className="text-xs opacity-70 mt-1">
              {new Date(message.timestamp).toLocaleTimeString('ja-JP', {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
