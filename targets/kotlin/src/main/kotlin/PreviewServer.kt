import com.sun.net.httpserver.HttpExchange
import com.sun.net.httpserver.HttpServer
import java.math.BigDecimal
import java.math.RoundingMode
import java.net.InetSocketAddress

// ── JSON helpers (dependency-free) ──────────────────────────────────────────

/** Minimal JSON serialiser for String/Int/BigDecimal/List/Map. */
private fun toJson(value: Any?): String = when (value) {
    is String -> "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""
    is Number -> value.toString()
    is Boolean -> value.toString()
    is Map<*, *> -> "{${value.entries.joinToString(",") { (k, v) -> "\"$k\":${toJson(v)}" }}}"
    is List<*> -> "[${value.joinToString(",") { toJson(it) }}]"
    null -> "null"
    else -> "\"$value\""
}

// ── Domain ───────────────────────────────────────────────────────────────────

data class Customer(val name: String, val tier: String)

/** Seeded customer table — server-side only; caller-supplied tier is ignored. */
private val CUSTOMERS: Map<Long, Customer> = mapOf(
    1L to Customer("Aster Office Supplies", "A"),
    2L to Customer("Merlion Retail",        "B"),
    3L to Customer("Straits Workshop",       "C")
)

/** Known product codes. Any line whose productCode is not in this set → 404. */
private val KNOWN_PRODUCTS: Set<String> = setOf("PAPER-A4", "CABLE-USB")

data class LineRequest(
    val lineNo: Int,
    val productCode: String,
    val qty: Int,
    val unitPrice: BigDecimal
)

data class PreviewRequest(
    val customerId: Long,
    val customer: Customer,
    val lines: List<LineRequest>
)

data class LineResult(
    val lineNo: Int,
    val productCode: String,
    val qty: Int,
    val unitPrice: BigDecimal,
    val lineNet: BigDecimal
)

data class PreviewResponse(
    val customerId: Long,
    val customerName: String,
    val tier: String,
    val subtotal: BigDecimal,
    val gst: BigDecimal,
    val total: BigDecimal,
    val lines: List<LineResult>
)

// ── Calculation ───────────────────────────────────────────────────────────────

private val TIER_DISCOUNT = mapOf(
    "A" to BigDecimal("0.05"),
    "B" to BigDecimal("0.03"),
    "C" to BigDecimal("0.00")
)
private val BULK_DISCOUNT = BigDecimal("0.02")
private val BULK_THRESHOLD = 100
private val GST_RATE = BigDecimal("0.09")
private val ONE = BigDecimal.ONE
private val SCALE = 2
private val UNIT_PRICE_SCALE = 4
private val HALF_UP = RoundingMode.HALF_UP

fun calculatePreview(req: PreviewRequest): PreviewResponse {
    val tier = req.customer.tier
    val tierDiscount = TIER_DISCOUNT[tier]!!      // always valid: customer.tier is seeded
    val tierFactor = ONE.subtract(tierDiscount)

    val lineResults = req.lines.map { line ->
        val gross = line.unitPrice.multiply(BigDecimal(line.qty))
        val afterTier = gross.multiply(tierFactor)
        val afterBulk = if (line.qty >= BULK_THRESHOLD) {
            afterTier.multiply(ONE.subtract(BULK_DISCOUNT))
        } else {
            afterTier
        }
        val lineNet = afterBulk.setScale(SCALE, HALF_UP)
        LineResult(
            lineNo = line.lineNo,
            productCode = line.productCode,
            qty = line.qty,
            unitPrice = line.unitPrice.setScale(UNIT_PRICE_SCALE, HALF_UP),
            lineNet = lineNet
        )
    }

    val subtotal = lineResults.fold(BigDecimal.ZERO) { acc, l -> acc.add(l.lineNet) }
        .setScale(SCALE, HALF_UP)
    val gst = subtotal.multiply(GST_RATE).setScale(SCALE, HALF_UP)
    val total = subtotal.add(gst).setScale(SCALE, HALF_UP)

    return PreviewResponse(
        customerId = req.customerId,
        customerName = req.customer.name,
        tier = tier,
        subtotal = subtotal,
        gst = gst,
        total = total,
        lines = lineResults
    )
}

// ── Minimal JSON parser ───────────────────────────────────────────────────────

class JsonParseException(msg: String) : RuntimeException(msg)

/**
 * Parses a JSON value from [src] starting at [pos], returns the parsed value
 * and the new position.  Supports object, array, string, number, boolean, null.
 * Raises JsonParseException on structural errors.
 */
private fun parseValue(src: String, pos: Int): Pair<Any?, Int> {
    val i = skipWs(src, pos)
    if (i >= src.length) throw JsonParseException("Unexpected end of input")
    return when (src[i]) {
        '{' -> parseObject(src, i)
        '[' -> parseArray(src, i)
        '"' -> parseString(src, i)
        't' -> {
            if (src.startsWith("true", i)) Pair(true, i + 4)
            else throw JsonParseException("Bad token at $i")
        }
        'f' -> {
            if (src.startsWith("false", i)) Pair(false, i + 5)
            else throw JsonParseException("Bad token at $i")
        }
        'n' -> {
            if (src.startsWith("null", i)) Pair(null, i + 4)
            else throw JsonParseException("Bad token at $i")
        }
        else -> parseNumber(src, i)
    }
}

private fun skipWs(src: String, pos: Int): Int {
    var i = pos
    while (i < src.length && src[i] in " \t\r\n") i++
    return i
}

private fun parseString(src: String, start: Int): Pair<String, Int> {
    require(src[start] == '"')
    val sb = StringBuilder()
    var i = start + 1
    while (i < src.length) {
        when (val c = src[i]) {
            '"' -> return Pair(sb.toString(), i + 1)
            '\\' -> {
                i++
                if (i >= src.length) throw JsonParseException("Bad escape")
                when (src[i]) {
                    '"' -> sb.append('"')
                    '\\' -> sb.append('\\')
                    '/' -> sb.append('/')
                    'n' -> sb.append('\n')
                    'r' -> sb.append('\r')
                    't' -> sb.append('\t')
                    'b' -> sb.append('\b')
                    'f' -> sb.append('\u000C')
                    'u' -> {
                        val hex = src.substring(i + 1, minOf(i + 5, src.length))
                        if (hex.length < 4) throw JsonParseException("Bad unicode")
                        sb.append(hex.toInt(16).toChar())
                        i += 4
                    }
                    else -> throw JsonParseException("Unknown escape \\${src[i]}")
                }
                i++
            }
            else -> { sb.append(c); i++ }
        }
    }
    throw JsonParseException("Unterminated string")
}

private fun parseNumber(src: String, start: Int): Pair<Any, Int> {
    var i = start
    if (i < src.length && src[i] == '-') i++
    while (i < src.length && src[i].isDigit()) i++
    val hasDot = i < src.length && src[i] == '.'
    if (hasDot) {
        i++
        while (i < src.length && src[i].isDigit()) i++
    }
    if (i < src.length && src[i] in "eE") {
        i++
        if (i < src.length && src[i] in "+-") i++
        while (i < src.length && src[i].isDigit()) i++
    }
    val raw = src.substring(start, i)
    if (raw.isEmpty()) throw JsonParseException("Expected number at $start")
    val value: Any = if (hasDot || raw.contains('e') || raw.contains('E')) {
        BigDecimal(raw)
    } else {
        raw.toLongOrNull() ?: throw JsonParseException("Bad number: $raw")
    }
    return Pair(value, i)
}

private fun parseObject(src: String, start: Int): Pair<Map<String, Any?>, Int> {
    require(src[start] == '{')
    val map = LinkedHashMap<String, Any?>()
    var i = skipWs(src, start + 1)
    if (i < src.length && src[i] == '}') return Pair(map, i + 1)
    while (true) {
        i = skipWs(src, i)
        if (src[i] != '"') throw JsonParseException("Expected key at $i")
        val (key, after) = parseString(src, i)
        i = skipWs(src, after)
        if (i >= src.length || src[i] != ':') throw JsonParseException("Expected ':' at $i")
        i = skipWs(src, i + 1)
        val (value, next) = parseValue(src, i)
        map[key] = value
        i = skipWs(src, next)
        when {
            i >= src.length -> throw JsonParseException("Unterminated object")
            src[i] == '}' -> return Pair(map, i + 1)
            src[i] == ',' -> i++
            else -> throw JsonParseException("Expected ',' or '}' at $i")
        }
    }
}

private fun parseArray(src: String, start: Int): Pair<List<Any?>, Int> {
    require(src[start] == '[')
    val list = mutableListOf<Any?>()
    var i = skipWs(src, start + 1)
    if (i < src.length && src[i] == ']') return Pair(list, i + 1)
    while (true) {
        val (value, next) = parseValue(src, i)
        list.add(value)
        i = skipWs(src, next)
        when {
            i >= src.length -> throw JsonParseException("Unterminated array")
            src[i] == ']' -> return Pair(list, i + 1)
            src[i] == ',' -> i = skipWs(src, i + 1)
            else -> throw JsonParseException("Expected ',' or ']' at $i")
        }
    }
}

// ── Request validation & parsing ──────────────────────────────────────────────

class ValidationException(msg: String) : RuntimeException(msg)
class NotFoundException(msg: String) : RuntimeException(msg)

@Suppress("UNCHECKED_CAST")
fun parseAndValidate(body: String): PreviewRequest {
    val root: Map<String, Any?> = try {
        val (v, _) = parseValue(body, 0)
        v as? Map<String, Any?> ?: throw ValidationException("Request must be a JSON object")
    } catch (e: JsonParseException) {
        throw ValidationException("Malformed JSON: ${e.message}")
    } catch (e: ClassCastException) {
        throw ValidationException("Request must be a JSON object")
    }

    val rawCustomerId = root["customerId"] ?: throw ValidationException("Missing customerId")
    val customerId: Long = when (rawCustomerId) {
        is Long -> rawCustomerId
        is Int  -> rawCustomerId.toLong()
        else    -> throw ValidationException("Invalid customerId")
    }

    // caller-supplied tier is silently ignored
    val customer = CUSTOMERS[customerId]
        ?: throw NotFoundException("Unknown customerId: $customerId")

    val rawLines = root["lines"]
        ?: throw ValidationException("Missing lines")
    val linesList = rawLines as? List<*>
        ?: throw ValidationException("lines must be an array")
    if (linesList.isEmpty()) throw ValidationException("lines must not be empty")

    val lines = linesList.mapIndexed { idx, item ->
        val lmap = item as? Map<*, *>
            ?: throw ValidationException("Line $idx must be an object")

        val productCode = (lmap["productCode"] as? String)
            ?: throw ValidationException("Line $idx: missing productCode")
        if (productCode !in KNOWN_PRODUCTS) throw NotFoundException("Unknown productCode: $productCode")

        val rawQty = lmap["qty"] ?: throw ValidationException("Line $idx: missing qty")
        // Reject strings and non-integer types
        if (rawQty is String) throw ValidationException("Line $idx: qty must be an integer, got string")
        if (rawQty is BigDecimal) throw ValidationException("Line $idx: qty must be an integer, got decimal")
        val qty: Int = when (rawQty) {
            is Long -> {
                if (rawQty <= 0) throw ValidationException("Line $idx: qty must be > 0")
                rawQty.toInt()
            }
            is Int -> {
                if (rawQty <= 0) throw ValidationException("Line $idx: qty must be > 0")
                rawQty
            }
            else -> throw ValidationException("Line $idx: qty must be an integer")
        }

        val rawUnit = lmap["unitPrice"] ?: throw ValidationException("Line $idx: missing unitPrice")
        val unitPrice: BigDecimal = when (rawUnit) {
            is BigDecimal -> rawUnit
            is Long -> BigDecimal(rawUnit)
            is String -> try { BigDecimal(rawUnit) } catch (e: NumberFormatException) {
                throw ValidationException("Line $idx: invalid unitPrice")
            }
            else -> throw ValidationException("Line $idx: invalid unitPrice")
        }
        if (unitPrice <= BigDecimal.ZERO) throw ValidationException("Line $idx: unitPrice must be > 0")

        LineRequest(
            lineNo = idx + 1,
            productCode = productCode,
            qty = qty,
            unitPrice = unitPrice
        )
    }

    return PreviewRequest(customerId = customerId, customer = customer, lines = lines)
}

// ── HTTP handlers ─────────────────────────────────────────────────────────────

private fun sendJson(ex: HttpExchange, status: Int, body: String) {
    val bytes = body.toByteArray(Charsets.UTF_8)
    ex.responseHeaders.set("Content-Type", "application/json; charset=utf-8")
    ex.sendResponseHeaders(status, bytes.size.toLong())
    ex.responseBody.use { it.write(bytes) }
}

private fun handleHealth(ex: HttpExchange) {
    if (ex.requestMethod != "GET") {
        ex.sendResponseHeaders(405, -1); ex.responseBody.close(); return
    }
    val json = toJson(mapOf("status" to "UP", "readOnly" to true, "writeCount" to 0))
    sendJson(ex, 200, json)
}

private fun handleInvoicePreview(ex: HttpExchange) {
    if (ex.requestMethod != "POST") {
        ex.sendResponseHeaders(405, -1); ex.responseBody.close(); return
    }
    val bodyText = ex.requestBody.use { it.readBytes().toString(Charsets.UTF_8) }
    val req = try {
        parseAndValidate(bodyText)
    } catch (e: ValidationException) {
        sendJson(ex, 400, toJson(mapOf("error" to e.message))); return
    } catch (e: NotFoundException) {
        sendJson(ex, 404, toJson(mapOf("error" to e.message))); return
    }
    val resp = calculatePreview(req)
    val lineJsonList = resp.lines.map { l ->
        mapOf(
            "lineNo" to l.lineNo,
            "productCode" to l.productCode,
            "qty" to l.qty,
            "unitPrice" to l.unitPrice.toPlainString(),
            "lineNet" to l.lineNet.toPlainString()
        )
    }
    val json = toJson(mapOf(
        "customerId" to resp.customerId,
        "customerName" to resp.customerName,
        "tier" to resp.tier,
        "subtotal" to resp.subtotal.toPlainString(),
        "gst" to resp.gst.toPlainString(),
        "total" to resp.total.toPlainString(),
        "lines" to lineJsonList
    ))
    sendJson(ex, 200, json)
}

// ── Entry point ───────────────────────────────────────────────────────────────

fun main(args: Array<String>) {
    var host = "127.0.0.1"
    var port = 19121
    var i = 0
    while (i < args.size) {
        when (args[i]) {
            "--host" -> { host = args[++i] }
            "--port" -> { port = args[++i].toInt() }
        }
        i++
    }

    val server = HttpServer.create(InetSocketAddress(host, port), 0)
    server.createContext("/internal/health") { ex ->
        if (ex.requestURI.path != "/internal/health") {
            ex.sendResponseHeaders(404, -1); ex.responseBody.close()
        } else {
            handleHealth(ex)
        }
    }
    server.createContext("/api/invoice-preview") { ex ->
        if (ex.requestURI.path != "/api/invoice-preview") {
            ex.sendResponseHeaders(404, -1); ex.responseBody.close()
        } else {
            handleInvoicePreview(ex)
        }
    }
    server.createContext("/") { ex ->
        ex.sendResponseHeaders(404, -1); ex.responseBody.close()
    }
    server.start()
    println("preview-service listening on $host:$port")
    // Stay in foreground
    Thread.currentThread().join()
}
