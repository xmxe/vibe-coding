package com.github.fq

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import com.github.fq.database.AppDatabase
import com.github.fq.database.DataItemDao
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel

class MyAccessibilityService : AccessibilityService() {

    private lateinit var db: AppDatabase
    private lateinit var dao: DataItemDao
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    private var lastEventTime = 0L
    private val DEBOUNCE_DELAY = 1000L // 减少延迟，更快响应
    private val targetPackageName = "com.android.chrome"

    companion object {
        @Volatile
        private var lastShownText: String? = null

        @Volatile
        private var lastShowTime = 0L
        private const val MIN_DISPLAY_INTERVAL = 1500L

        fun isAccessibilityEnabled(context: Context): Boolean {
            val manager = context.getSystemService(Context.ACCESSIBILITY_SERVICE) as? android.view.accessibility.AccessibilityManager
                ?: return false
            val services = manager.getEnabledAccessibilityServiceList(AccessibilityServiceInfo.FEEDBACK_ALL_MASK)
            return services.any { info ->
                info.resolveInfo.serviceInfo.packageName == context.packageName
            }
        }
    }

    private val handler = Handler(Looper.getMainLooper())

    // 防抖用的 Runnable
    private val fetchAndShowTextRunnable = Runnable { fetchAndShowText() }
    private val hideWindowRunnable = Runnable { FloatWindowManager.hideWindow() }

    override fun onServiceConnected() {
        super.onServiceConnected()

        db = AppDatabase.getDatabase(this)
        dao = db.dataItemDao()
        Log.d("MyAccessibilityService", "无障碍服务已连接")

        serviceInfo = AccessibilityServiceInfo().apply {
            eventTypes = AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED or
                    AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED or
                    AccessibilityEvent.TYPE_VIEW_SCROLLED

            // 可监听所有 App，因为我们自己判断包名
            packageNames = null // 监听所有，避免漏掉切换事件
            flags = AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS
            notificationTimeout = 100
        }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        val eventType = event?.eventType ?: return
        val packageName = event.packageName?.toString() ?: return

        if (packageName == this.packageName) {
            Log.d("MyAccessibilityService", "🟡 忽略自身事件: $eventType, 包名: $packageName")
            return
        }
        // Log.d("MyAccessibilityService", "✅ 外部事件: $eventType, 包名: $packageName")
        // === 关键逻辑：根据包名控制悬浮窗显隐 ===
        if (packageName != targetPackageName) {
            // 不是 Chrome，延迟关闭（防抖）
            handler.removeCallbacks(hideWindowRunnable)
            handler.postDelayed(hideWindowRunnable, 300)
            return
        }

        // 是 Chrome，清除关闭任务
        handler.removeCallbacks(hideWindowRunnable)

        // 防抖：避免频繁刷新
        val currentTime = System.currentTimeMillis()
        if (currentTime - lastEventTime < DEBOUNCE_DELAY) return
        lastEventTime = currentTime

        // 延迟刷新内容（避免事件风暴）
        handler.removeCallbacks(fetchAndShowTextRunnable)
        handler.postDelayed(fetchAndShowTextRunnable, 200)
    }

    private fun fetchAndShowText() {
        val rootNode = rootInActiveWindow ?: return

        // 再次确认是 Chrome
        val windowPackageName = rootNode.packageName?.toString()
        if (windowPackageName != targetPackageName) {
            FloatWindowManager.hideWindow()
            rootNode.recycle()
            return
        }

        val textSet = hashSetOf<String>()
        collectTextFromNode(rootNode, textSet)

        if (isFloatWindowEnabled() && textSet.isNotEmpty() && shouldShowText(textSet)) {
            val content = textSet.joinToString("\n")
            FloatWindowManager.showWindow(this, content)
            // Log.d("MyAccessibilityService", "✅ 悬浮窗已显示: $content")
        }

        rootNode.recycle()
    }
    private fun isFloatWindowEnabled(): Boolean {
        val sp = getSharedPreferences("config", Context.MODE_PRIVATE)
        return sp.getBoolean("enable_float_window", false) // 默认关闭
    }


    private fun shouldShowText(texts: Set<String>): Boolean {
        val currentTime = System.currentTimeMillis()
        val combinedText = texts.joinToString(" ")

        if (combinedText == lastShownText && currentTime - lastShowTime < MIN_DISPLAY_INTERVAL) {
            return false
        }
        lastShownText = combinedText
        lastShowTime = currentTime
        return true
    }

    private fun collectTextFromNode(node: AccessibilityNodeInfo, texts: HashSet<String>) {
        node.text?.toString()?.trim()?.takeIf { it.isNotEmpty() }?.let { texts.add(it) }
        node.contentDescription?.toString()?.trim()?.takeIf { it.isNotEmpty() }
            ?.let { texts.add(it) }

        for (i in 0 until node.childCount) {
            val child = node.getChild(i)
            if (child != null) {
                try {
                    collectTextFromNode(child, texts)
                } catch (e: Exception) {
                    Log.e("MyAccessibilityService", "遍历子节点时出错: $i", e)
                } finally {
                    child.recycle()
                }
            }
        }
    }

    override fun onInterrupt() {
        // Log.d("MyAccessibilityService", "服务被中断")
        scope.cancel()
        FloatWindowManager.hideWindow()
    }

    override fun onDestroy() {
        super.onDestroy()
        scope.cancel()
        handler.removeCallbacksAndMessages(null) // 清除所有任务
        FloatWindowManager.hideWindow()
        // Log.d("MyAccessibilityService", "服务已销毁")
    }

    override fun onUnbind(intent: Intent?): Boolean {
        handler.removeCallbacksAndMessages(null)
        FloatWindowManager.hideWindow()
        return super.onUnbind(intent)
    }
}