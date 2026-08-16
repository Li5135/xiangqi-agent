package com.xiangqi.click

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import com.sun.net.httpserver.HttpExchange
import com.sun.net.httpserver.HttpServer
import org.json.JSONObject
import java.net.InetSocketAddress
import java.util.concurrent.Executors

/**
 * 无障碍点击服务：在 127.0.0.1:8123 提供 HTTP 接口，
 * 接收 Termux Python 进程发来的点击/滑动指令并模拟手势。
 *
 *  POST /tap    {"x":100,"y":200}
 *  POST /swipe  {"from":[x,y],"to":[x,y],"duration":300}
 *  GET  /health -> 200 ok
 */
class ClickServerService : AccessibilityService() {

    private var server: HttpServer? = null
    private val mainHandler = Handler(Looper.getMainLooper())

    override fun onServiceConnected() {
        super.onServiceConnected()
        startServer()
    }

    private fun startServer() {
        try {
            val s = HttpServer.create(InetSocketAddress("127.0.0.1", PORT), 0)
            s.executor = Executors.newFixedThreadPool(2)
            s.createContext("/health") { ex -> respond(ex, 200, "ok") }
            s.createContext("/tap") { ex ->
                try {
                    val j = JSONObject(ex.requestBody.readBytes().toString(Charsets.UTF_8))
                    dispatchTap(j.getDouble("x").toFloat(), j.getDouble("y").toFloat())
                    respond(ex, 200, "ok")
                } catch (e: Exception) {
                    respond(ex, 400, e.message ?: "bad request")
                }
            }
            s.createContext("/swipe") { ex ->
                try {
                    val j = JSONObject(ex.requestBody.readBytes().toString(Charsets.UTF_8))
                    val from = j.getJSONArray("from")
                    val to = j.getJSONArray("to")
                    dispatchSwipe(
                        from.getDouble(0).toFloat(), from.getDouble(1).toFloat(),
                        to.getDouble(0).toFloat(), to.getDouble(1).toFloat(),
                        j.optLong("duration", 300L)
                    )
                    respond(ex, 200, "ok")
                } catch (e: Exception) {
                    respond(ex, 400, e.message ?: "bad request")
                }
            }
            s.start()
            server = s
            Log.i(TAG, "ClickServer listening on 127.0.0.1:$PORT")
        } catch (e: Exception) {
            Log.e(TAG, "server start failed", e)
        }
    }

    /** dispatchGesture 必须在主线程调用。 */
    private fun dispatchTap(x: Float, y: Float) {
        mainHandler.post {
            val path = Path().apply { moveTo(x, y) }
            val stroke = GestureDescription.StrokeDescription(path, 0, 100)
            val gesture = GestureDescription.Builder().addStroke(stroke).build()
            dispatchGesture(gesture, null, null)
        }
    }

    private fun dispatchSwipe(x1: Float, y1: Float, x2: Float, y2: Float, duration: Long) {
        mainHandler.post {
            val path = Path().apply { moveTo(x1, y1); lineTo(x2, y2) }
            val stroke = GestureDescription.StrokeDescription(path, 0, duration)
            val gesture = GestureDescription.Builder().addStroke(stroke).build()
            dispatchGesture(gesture, null, null)
        }
    }

    private fun respond(ex: HttpExchange, code: Int, body: String) {
        val bytes = body.toByteArray()
        ex.sendResponseHeaders(code, bytes.size.toLong())
        ex.responseBody.use { it.write(bytes) }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit
    override fun onInterrupt() = Unit

    override fun onDestroy() {
        server?.stop(0)
        super.onDestroy()
    }

    companion object {
        private const val TAG = "ClickServer"
        private const val PORT = 8123
    }
}
