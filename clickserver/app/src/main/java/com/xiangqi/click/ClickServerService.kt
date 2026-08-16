package com.xiangqi.click

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import fi.iki.elonen.NanoHTTPD
import org.json.JSONObject

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

    /** NanoHTTPD 服务端。 */
    inner class HttpServer : NanoHTTPD("127.0.0.1", PORT) {
        override fun serve(session: NanoHTTPD.IHTTPSession): Response {
            return try {
                when (session.uri) {
                    "/health" -> newFixedLengthResponse(Response.Status.OK, "text/plain", "ok")
                    "/tap" -> {
                        val j = JSONObject(readBody(session))
                        dispatchTap(j.getDouble("x").toFloat(), j.getDouble("y").toFloat())
                        newFixedLengthResponse(Response.Status.OK, "text/plain", "ok")
                    }
                    "/swipe" -> {
                        val j = JSONObject(readBody(session))
                        val from = j.getJSONArray("from")
                        val to = j.getJSONArray("to")
                        dispatchSwipe(
                            from.getDouble(0).toFloat(), from.getDouble(1).toFloat(),
                            to.getDouble(0).toFloat(), to.getDouble(1).toFloat(),
                            j.optLong("duration", 300L)
                        )
                        newFixedLengthResponse(Response.Status.OK, "text/plain", "ok")
                    }
                    else -> newFixedLengthResponse(Response.Status.NOT_FOUND, "text/plain", "not found")
                }
            } catch (e: Exception) {
                Log.w(TAG, "handle ${session.uri} failed", e)
                newFixedLengthResponse(
                    Response.Status.BAD_REQUEST, "text/plain",
                    e.message ?: "bad request"
                )
            }
        }
    }

    private fun readBody(session: NanoHTTPD.IHTTPSession): String {
        val len = session.headers["content-length"]?.toIntOrNull() ?: 0
        if (len <= 0) return ""
        val bytes = ByteArray(len)
        var off = 0
        while (off < len) {
            val n = session.inputStream.read(bytes, off, len - off)
            if (n < 0) break
            off += n
        }
        return String(bytes, 0, off, Charsets.UTF_8)
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        startServer()
    }

    private fun startServer() {
        try {
            val s = HttpServer()
            s.start(SOCKET_READ_TIMEOUT, false)
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

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit
    override fun onInterrupt() = Unit

    override fun onDestroy() {
        server?.stop()
        super.onDestroy()
    }

    companion object {
        private const val TAG = "ClickServer"
        private const val PORT = 8123
        private const val SOCKET_READ_TIMEOUT = 10_000
    }
}
