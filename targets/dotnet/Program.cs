using System.Text.Json;
using System.Text.Json.Serialization;

var builder = WebApplication.CreateBuilder(args);
builder.Services.ConfigureHttpJsonOptions(o =>
{
    o.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
});

var app = builder.Build();

// ── Health ────────────────────────────────────────────────────────────────────

app.MapGet("/internal/health", () =>
    Results.Ok(new HealthResponse("UP", true, 0)));

// ── Invoice preview ───────────────────────────────────────────────────────────

app.MapPost("/api/invoice-preview", async (HttpRequest request) =>
{
    InvoiceRequest? req;
    try
    {
        req = await request.ReadFromJsonAsync<InvoiceRequest>(
            PreviewSerializerContext.Default.InvoiceRequest);
    }
    catch (JsonException)
    {
        return Results.Json(new { error = "Bad Request" }, statusCode: 400);
    }
    catch (Exception)
    {
        return Results.Json(new { error = "Bad Request" }, statusCode: 400);
    }

    if (req is null)
        return Results.Json(new { error = "Bad Request" }, statusCode: 400);

    var error = req.Validate();
    if (error is not null)
        return Results.Json(new { error }, statusCode: 400);

    // Resolve customer server-side; caller-supplied tier is ignored.
    if (!CustomerCatalog.TryGet(req.CustomerId!.Value, out var customer))
        return Results.Json(new { error = "Customer not found" }, statusCode: 404);

    // Validate product codes.
    foreach (var line in req.Lines!)
    {
        if (!ProductCatalog.IsKnown(line.ProductCode))
            return Results.Json(new { error = $"Product not found: {line.ProductCode}" }, statusCode: 404);
    }

    return Results.Ok(Preview.Calculate(req, customer));
});

// ── Reject undeclared routes and write methods ────────────────────────────────

app.MapFallback(() => Results.StatusCode(405));

app.Run();

// ── Customer catalog ──────────────────────────────────────────────────────────

record Customer(int Id, string Name, string Tier);

static class CustomerCatalog
{
    private static readonly Dictionary<int, Customer> _map = new()
    {
        [1] = new Customer(1, "Aster Office Supplies", "A"),
        [2] = new Customer(2, "Merlion Retail",        "B"),
        [3] = new Customer(3, "Straits Workshop",      "C"),
    };

    internal static bool TryGet(int id, out Customer customer)
        => _map.TryGetValue(id, out customer!);
}

// ── Product catalog ───────────────────────────────────────────────────────────

static class ProductCatalog
{
    private static readonly HashSet<string> _known = new(StringComparer.OrdinalIgnoreCase)
    {
        "PAPER-A4",
        "CABLE-USB",
    };

    internal static bool IsKnown(string? code)
        => code is not null && _known.Contains(code);
}

// ── Domain / request types ────────────────────────────────────────────────────

record HealthResponse(
    [property: JsonPropertyName("status")]   string Status,
    [property: JsonPropertyName("readOnly")] bool ReadOnly,
    [property: JsonPropertyName("writeCount")] int WriteCount);

record InvoiceRequest(
    [property: JsonPropertyName("customerId")] int?           CustomerId,
    [property: JsonPropertyName("tier")]        string?        Tier,
    [property: JsonPropertyName("lines")]       List<LineItem>? Lines);

record LineItem(
    [property: JsonPropertyName("lineNo")]      int?    LineNo,
    [property: JsonPropertyName("productCode")] string? ProductCode,
    [property: JsonPropertyName("qty")]         int?    Qty,
    [property: JsonPropertyName("unitPrice")]   string? UnitPrice);

// ── Response types ────────────────────────────────────────────────────────────

record PreviewResponse(
    [property: JsonPropertyName("customerId")]   int    CustomerId,
    [property: JsonPropertyName("customerName")] string CustomerName,
    [property: JsonPropertyName("tier")]          string Tier,
    [property: JsonPropertyName("subtotal")]      string Subtotal,
    [property: JsonPropertyName("gst")]           string Gst,
    [property: JsonPropertyName("total")]         string Total,
    [property: JsonPropertyName("lines")]         List<LineDto> Lines);

record LineDto(
    [property: JsonPropertyName("lineNo")]      int    LineNo,
    [property: JsonPropertyName("productCode")] string ProductCode,
    [property: JsonPropertyName("qty")]         int    Qty,
    [property: JsonPropertyName("unitPrice")]   string UnitPrice,
    [property: JsonPropertyName("lineNet")]     string LineNet);

// ── Validation ────────────────────────────────────────────────────────────────

static class InvoiceRequestExtensions
{
    internal static string? Validate(this InvoiceRequest req)
    {
        if (req.CustomerId is null)
            return "customerId is required";
        if (req.Lines is null || req.Lines.Count == 0)
            return "lines are required";
        foreach (var line in req.Lines)
        {
            if (line.Qty is null || line.Qty.Value <= 0)
                return "qty must be a positive integer";
            if (line.UnitPrice is null ||
                !decimal.TryParse(line.UnitPrice,
                    System.Globalization.NumberStyles.Number,
                    System.Globalization.CultureInfo.InvariantCulture,
                    out var up) || up <= 0m)
                return "unitPrice must be a positive decimal string";
        }
        return null;
    }
}

// ── Pricing engine ────────────────────────────────────────────────────────────

static class Preview
{
    private static readonly decimal GstRate = 0.09m;

    internal static PreviewResponse Calculate(InvoiceRequest req, Customer customer)
    {
        decimal tierDiscount = customer.Tier switch
        {
            "A" => 0.05m,
            "B" => 0.03m,
            _   => 0.00m
        };

        var lines = new List<LineDto>();
        int lineNo = 1;
        decimal subtotal = 0m;

        foreach (var item in req.Lines!)
        {
            int qty = item.Qty!.Value;
            decimal unitPrice = decimal.Parse(
                item.UnitPrice!,
                System.Globalization.NumberStyles.Number,
                System.Globalization.CultureInfo.InvariantCulture);

            decimal discounted = unitPrice * (1m - tierDiscount);
            if (qty >= 100)
                discounted = discounted * 0.98m;

            decimal lineNet = decimal.Round(discounted * qty, 2, MidpointRounding.AwayFromZero);
            subtotal += lineNet;

            lines.Add(new LineDto(
                lineNo++,
                item.ProductCode ?? "",
                qty,
                unitPrice.ToString("F4", System.Globalization.CultureInfo.InvariantCulture),
                lineNet.ToString("F2", System.Globalization.CultureInfo.InvariantCulture)));
        }

        subtotal = decimal.Round(subtotal, 2, MidpointRounding.AwayFromZero);
        decimal gst = decimal.Round(subtotal * GstRate, 2, MidpointRounding.AwayFromZero);
        decimal total = subtotal + gst;

        return new PreviewResponse(
            customer.Id,
            customer.Name,
            customer.Tier,
            subtotal.ToString("F2"),
            gst.ToString("F2"),
            total.ToString("F2"),
            lines);
    }
}

// ── Source-generated JSON context ─────────────────────────────────────────────

[JsonSerializable(typeof(InvoiceRequest))]
[JsonSerializable(typeof(List<LineItem>))]
[JsonSerializable(typeof(PreviewResponse))]
[JsonSerializable(typeof(List<LineDto>))]
[JsonSerializable(typeof(HealthResponse))]
[JsonSourceGenerationOptions(PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase)]
internal partial class PreviewSerializerContext : JsonSerializerContext { }

public partial class Program { }
