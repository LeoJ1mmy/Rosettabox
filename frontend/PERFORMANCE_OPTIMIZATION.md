# 前端性能優化建議

## 當前渲染任務分配

### 客戶端（瀏覽器）- 約 70-80%
- React 組件渲染和虛擬 DOM 計算
- 狀態管理（useState, useEffect）
- DOM 操作和樣式計算
- 用戶交互響應
- localStorage 存儲管理
- WebSocket 連接（如果有）

### 服務器端 - 約 20-30%
- API 數據處理
- 任務狀態查詢
- 文件處理和 AI 模型運算
- 數據庫查詢

## 主要性能問題

### 1. 隊列頁面整體重載問題
**問題描述**：每次切換標籤頁時，整個組件都會重新載入，導致不必要的 API 請求和 DOM 重渲染。

**優化方案**：
```javascript
// 使用 React.memo 優化組件
const TaskItem = React.memo(({ task }) => {
  // 組件邏輯
}, (prevProps, nextProps) => {
  // 自定義比較邏輯，只在必要時重渲染
  return prevProps.task.id === nextProps.task.id &&
         prevProps.task.status === nextProps.task.status;
});
```

### 2. 不必要的狀態更新
**問題描述**：即使數據沒有變化，也會觸發組件重渲染。

**優化方案**：
```javascript
// 使用函數式更新和深度比較
setUserTasks(prev => {
  const newTasks = response.data.user_tasks;
  if (JSON.stringify(prev) !== JSON.stringify(newTasks)) {
    return newTasks;
  }
  return prev; // 返回相同引用，避免重渲染
});
```

### 3. 頻繁的 API 請求
**問題描述**：每 3 秒請求一次，即使沒有活動任務。

**優化方案**：
```javascript
// 智能刷新頻率
const hasActiveTasks = tasks.some(t => t.status === 'processing');
const refreshInterval = hasActiveTasks ? 3000 : 10000; // 有任務3秒，無任務10秒
```

## 實施的優化措施

### 1. 組件拆分和 memo 化
- 將大組件拆分為小組件
- 使用 `React.memo` 包裝組件
- 實現自定義比較函數

### 2. 狀態管理優化
- 使用 `useCallback` 緩存函數
- 使用 `useMemo` 緩存計算結果
- 避免在渲染期間創建新對象

### 3. 虛擬滾動（如需要）
對於大量任務列表，可以實施虛擬滾動：
```javascript
import { FixedSizeList } from 'react-window';

<FixedSizeList
  height={600}
  itemCount={tasks.length}
  itemSize={80}
>
  {({ index, style }) => (
    <TaskItem style={style} task={tasks[index]} />
  )}
</FixedSizeList>
```

### 4. 懶加載和代碼分割
```javascript
// 懶加載隊列頁面
const QueuePage = React.lazy(() => import('./pages/QueuePage'));

// 使用 Suspense 包裝
<Suspense fallback={<Loading />}>
  <QueuePage />
</Suspense>
```

### 5. 局部狀態更新
使用 `useReducer` 或狀態管理庫（如 Zustand）來管理複雜狀態：
```javascript
const [state, dispatch] = useReducer(queueReducer, initialState);

// 只更新改變的部分
dispatch({ type: 'UPDATE_TASK', payload: { id: taskId, changes } });
```

## 性能監控

### 使用 React DevTools Profiler
1. 安裝 React DevTools 擴展
2. 使用 Profiler 標籤分析渲染性能
3. 找出渲染耗時最長的組件

### 添加性能監控代碼
```javascript
// 監控組件渲染次數
useEffect(() => {
  console.count('QueuePage rendered');
});

// 監控 API 請求時間
const startTime = performance.now();
const response = await fetch('/api/...');
console.log(`API 請求耗時: ${performance.now() - startTime}ms`);
```

## 建議實施順序

1. **立即實施**：使用 OptimizedQueuePage 替換原有 QueuePage
2. **短期優化**：添加 React.memo 到所有列表項組件
3. **中期優化**：實施智能刷新頻率和局部狀態更新
4. **長期優化**：考慮使用狀態管理庫和虛擬滾動

## 預期效果

- 減少 50-70% 的不必要重渲染
- 減少 30-50% 的 API 請求
- 提升用戶體驗的流暢度
- 降低客戶端 CPU 和內存使用