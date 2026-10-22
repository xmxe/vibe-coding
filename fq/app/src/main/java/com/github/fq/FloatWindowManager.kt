package com.github.fq

import android.annotation.SuppressLint
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.graphics.PixelFormat
import android.os.Build
import android.provider.Settings
import android.util.DisplayMetrics
import android.util.Log
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.TextView
import android.widget.Toast

@SuppressLint("StaticFieldLeak")
object FloatWindowManager {

    private var windowManager: WindowManager? = null
    private var floatView: View? = null
    private var context: Context? = null
    private var isExpanded = false
    private var initialTouchX = 0f
    private var initialTouchY = 0f

    private const val PREF_NAME = "float_window_pref"
    private const val KEY_X = "float_window_x"
    private const val KEY_Y = "float_window_y"

    private fun savePosition(x: Int, y: Int) {
        context?.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
            ?.edit()
            ?.putInt(KEY_X, x)
            ?.putInt(KEY_Y, y)
            ?.apply()
    }

    private fun loadPosition(): Pair<Int, Int> {
        val prefs = context?.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE) ?: return 0 to 100
        val x = prefs.getInt(KEY_X, 0)
        val y = prefs.getInt(KEY_Y, 100)
        return x to y
    }

    /**
     * 显示悬浮窗
     */
    @SuppressLint("ClickableViewAccessibility")
    fun showWindow(appContext: Context, text: String) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(appContext)) {
            Toast.makeText(appContext, "需要“悬浮窗”权限，请在设置中开启", Toast.LENGTH_LONG).show()
            return
        }
        if (isShowing()) hideWindow()

        // 使用 ApplicationContext，避免内存泄漏
        this.context = appContext.applicationContext
        val ctx = this.context ?: throw IllegalStateException("Context cannot be null")

        val layoutInflater = ctx.getSystemService(Context.LAYOUT_INFLATER_SERVICE) as LayoutInflater
        floatView = layoutInflater.inflate(R.layout.float_window_layout, null)

        val textView = floatView?.findViewById<TextView>(R.id.textView)
        val btnClose = floatView?.findViewById<Button>(R.id.btnClose)
        // val btnExpand = floatView?.findViewById<Button>(R.id.btnExpand)
        val btnCopy = floatView?.findViewById<Button>(R.id.btnCopy)

        textView?.text = text

        val (savedX, savedY) = loadPosition()
        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            else
                WindowManager.LayoutParams.TYPE_PHONE,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS, // 允许移出屏幕边界
            PixelFormat.TRANSLUCENT
        )

        params.x = savedX
        params.y = savedY

        windowManager = ctx.getSystemService(Context.WINDOW_SERVICE) as WindowManager

        // 拖动实现
        floatView?.setOnTouchListener { view, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    initialTouchX = event.rawX - params.x
                    initialTouchY = event.rawY - params.y
                    true
                }

                MotionEvent.ACTION_MOVE -> {
                    params.x = (event.rawX - initialTouchX).toInt()
                    params.y = (event.rawY - initialTouchY).toInt()

                    // 边界检查（即使有FLAG_LAYOUT_NO_LIMITS也建议保留）
                    val displayMetrics = DisplayMetrics()
                    windowManager?.defaultDisplay?.getMetrics(displayMetrics)
                    val screenWidth = displayMetrics.widthPixels
                    val screenHeight = displayMetrics.heightPixels

                    val view = floatView ?: return@setOnTouchListener true

                    // 允许向上拖动（负值）
                    params.x = params.x.coerceIn(-view.width / 2, screenWidth - view.width / 2)
                    // params.y = params.y.coerceIn(-view.height / 2, screenHeight - view.height / 2)

                    windowManager?.updateViewLayout(floatView, params)
                    true
                }

                MotionEvent.ACTION_UP -> {
                    autoSnapToEdge(params, view)
                    savePosition(params.x, params.y)
                    true
                }

                else -> false
            }
        }

        btnClose?.setOnClickListener {
            hideWindow()
        }

        btnCopy?.setOnClickListener {
            val content = textView?.text.toString()
            if (content.isNotEmpty()) {
                val clipboard = ctx.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                val clip = ClipData.newPlainText("copied_text", content)
                clipboard.setPrimaryClip(clip)
                Toast.makeText(ctx, "已复制到剪贴板", Toast.LENGTH_SHORT).show()
            } else {
                Toast.makeText(ctx, "没有内容可复制", Toast.LENGTH_SHORT).show()
            }
        }

        // btnExpand?.setOnClickListener {
        //     isExpanded = !isExpanded
        //     if (isExpanded) {
        //         textView?.text = "【详细信息】\n$text\n这是展开后的内容。"
        //         btnExpand.text = "收起"
        //     } else {
        //         textView?.text = text
        //         btnExpand.text = "展开"
        //     }
        //     params.height = WindowManager.LayoutParams.WRAP_CONTENT
        //     windowManager?.updateViewLayout(floatView, params)
        // }

        try {
            windowManager?.addView(floatView, params)
        } catch (e: Exception) {
            Toast.makeText(ctx, "无法显示悬浮窗，请检查权限", Toast.LENGTH_LONG).show()
            e.printStackTrace()
        }
    }

    /**
     * 自动吸附到屏幕边缘
     */
    private fun autoSnapToEdge(params: WindowManager.LayoutParams, view: View) {
        val displayMetrics = DisplayMetrics()
        windowManager?.defaultDisplay?.getMetrics(displayMetrics)
        val screenWidth = displayMetrics.widthPixels
        val screenHeight = displayMetrics.heightPixels

        // X 轴吸附
        val viewCenterX = params.x + view.width / 2
        params.x = if (viewCenterX < screenWidth / 2) 0 else screenWidth - view.width

        windowManager?.updateViewLayout(floatView, params)
    }

    /**
     * 隐藏悬浮窗并清理引用
     */
    fun hideWindow() {
        if (!isShowing()) {
            return
        }

        try {
            if (windowManager != null && floatView?.parent != null) {
                windowManager?.removeView(floatView)
                // Log.d("FloatWindowManager", "✅ 悬浮窗已成功移除")
            } else {
                Log.d("FloatWindowManager", "⚠️ windowManager 为 null 或 view 已 detached")
            }
        } catch (e: Exception) {
            Log.e("FloatWindowManager", "移除悬浮窗失败", e)
        } finally {
            floatView = null
            windowManager = null
            context = null
            isExpanded = false
        }
    }

    /**
     * 判断悬浮窗是否正在显示
     */
    fun isShowing(): Boolean = floatView != null
}