using System.Net;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

namespace PreviewApi.Tests;

public class PreviewContractTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient _client;

    public PreviewContractTests(WebApplicationFactory<Program> factory)
    {
        _client = factory.CreateClient();
    }

    // ── Health ────────────────────────────────────────────────────────────────

    [Fact]
    public async Task Health_Returns200_WithExpectedFields()
    {
        var response = await _client.GetAsync("/internal/health");
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        var root = doc.RootElement;

        Assert.Equal("UP",    root.GetProperty("status").GetString());
        Assert.True(          root.GetProperty("readOnly").GetBoolean());
        Assert.Equal(0,       root.GetProperty("writeCount").GetInt32());
    }

    [Fact]
    public async Task Health_DoesNotIncrementWriteCount()
    {
        await _client.GetAsync("/internal/health");
        await _client.GetAsync("/internal/health");

        var response = await _client.GetAsync("/internal/health");
        var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        Assert.Equal(0, doc.RootElement.GetProperty("writeCount").GetInt32());
    }

    // ── Totals ────────────────────────────────────────────────────────────────

    [Fact]
    public async Task Preview_Qty99_TierA_ReturnsCorrectTotals()
    {
        // No tier in request — server resolves from customerId=1 (Aster, tier A)
        var body = new
        {
            customerId = 1,
            lines = new[] { new { productCode = "PAPER-A4", qty = 99, unitPrice = "10.00" } }
        };
        var result = await PostPreview(body);

        Assert.Equal("940.50",  result.GetProperty("subtotal").GetString());
        Assert.Equal("84.65",   result.GetProperty("gst").GetString());
        Assert.Equal("1025.15", result.GetProperty("total").GetString());
    }

    [Fact]
    public async Task Preview_Qty100_TierA_ReturnsCorrectTotals()
    {
        var body = new
        {
            customerId = 1,
            lines = new[] { new { productCode = "PAPER-A4", qty = 100, unitPrice = "10.00" } }
        };
        var result = await PostPreview(body);

        Assert.Equal("931.00",  result.GetProperty("subtotal").GetString());
        Assert.Equal("83.79",   result.GetProperty("gst").GetString());
        Assert.Equal("1014.79", result.GetProperty("total").GetString());
    }

    [Fact]
    public async Task Preview_Qty101_TierA_ReturnsCorrectTotals()
    {
        var body = new
        {
            customerId = 1,
            lines = new[] { new { productCode = "PAPER-A4", qty = 101, unitPrice = "10.00" } }
        };
        var result = await PostPreview(body);

        Assert.Equal("940.31",  result.GetProperty("subtotal").GetString());
        Assert.Equal("84.63",   result.GetProperty("gst").GetString());
        Assert.Equal("1024.94", result.GetProperty("total").GetString());
    }

    [Fact]
    public async Task Preview_Rounding_5x3point3350_TierA()
    {
        var body = new
        {
            customerId = 1,
            lines = new[] { new { productCode = "CABLE-USB", qty = 5, unitPrice = "3.3350" } }
        };
        var result = await PostPreview(body);

        Assert.Equal("15.84", result.GetProperty("subtotal").GetString());
        Assert.Equal("1.43",  result.GetProperty("gst").GetString());
        Assert.Equal("17.27", result.GetProperty("total").GetString());
    }

    // ── Line format: unitPrice four decimals, lineNet two decimals ────────────

    [Fact]
    public async Task Preview_Qty99_TierA_LineUnitPriceFourDecimals()
    {
        var body = new
        {
            customerId = 1,
            lines = new[] { new { productCode = "PAPER-A4", qty = 99, unitPrice = "10.00" } }
        };
        var result = await PostPreview(body);

        var line = result.GetProperty("lines")[0];
        Assert.Equal("10.0000", line.GetProperty("unitPrice").GetString());
        Assert.Equal("940.50",  line.GetProperty("lineNet").GetString());
    }

    [Fact]
    public async Task Preview_Qty100_TierA_LineUnitPriceFourDecimals()
    {
        var body = new
        {
            customerId = 1,
            lines = new[] { new { productCode = "PAPER-A4", qty = 100, unitPrice = "10.00" } }
        };
        var result = await PostPreview(body);

        var line = result.GetProperty("lines")[0];
        Assert.Equal("10.0000", line.GetProperty("unitPrice").GetString());
        Assert.Equal("931.00",  line.GetProperty("lineNet").GetString());
    }

    [Fact]
    public async Task Preview_Rounding_5x3point3350_TierA_LineFourDecimals()
    {
        var body = new
        {
            customerId = 1,
            lines = new[] { new { productCode = "CABLE-USB", qty = 5, unitPrice = "3.3350" } }
        };
        var result = await PostPreview(body);

        var line = result.GetProperty("lines")[0];
        Assert.Equal("3.3350", line.GetProperty("unitPrice").GetString());
        Assert.Equal("15.84",  line.GetProperty("lineNet").GetString());
    }

    [Fact]
    public async Task Preview_TierB_ReturnsCorrectTotals()
    {
        var body = new
        {
            customerId = 2,
            lines = new[] { new { productCode = "PAPER-A4", qty = 1, unitPrice = "10.00" } }
        };
        var result = await PostPreview(body);

        Assert.Equal("9.70",  result.GetProperty("subtotal").GetString());
        Assert.Equal("0.87",  result.GetProperty("gst").GetString());
        Assert.Equal("10.57", result.GetProperty("total").GetString());
    }

    [Fact]
    public async Task Preview_TierC_ReturnsCorrectTotals()
    {
        var body = new
        {
            customerId = 3,
            lines = new[] { new { productCode = "PAPER-A4", qty = 1, unitPrice = "10.00" } }
        };
        var result = await PostPreview(body);

        Assert.Equal("10.00", result.GetProperty("subtotal").GetString());
        Assert.Equal("0.90",  result.GetProperty("gst").GetString());
        Assert.Equal("10.90", result.GetProperty("total").GetString());
    }

    // ── Server-side customer resolution ───────────────────────────────────────

    [Fact]
    public async Task Preview_NoTierInRequest_Returns200_ServerResolvesCustomer()
    {
        // Legacy payload: no tier field; server must resolve from customerId.
        const string json = """{"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":1,"unitPrice":"10.00"}]}""";
        var response = await _client.PostAsync("/api/invoice-preview",
            new StringContent(json, Encoding.UTF8, "application/json"));
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        var root = doc.RootElement;
        Assert.Equal("Aster Office Supplies", root.GetProperty("customerName").GetString());
        Assert.Equal("A",                     root.GetProperty("tier").GetString());
        Assert.Equal("9.50",                  root.GetProperty("subtotal").GetString());
    }

    [Fact]
    public async Task Preview_CallerTierIgnored_ServerUsesOwnTier()
    {
        // Contract case "caller-tier-ignored": customerId=1 is tier A;
        // caller supplies tier=C which must be ignored.
        const string json = """{"customerId":1,"tier":"C","lines":[{"productCode":"PAPER-A4","qty":1,"unitPrice":"10.00"}]}""";
        var response = await _client.PostAsync("/api/invoice-preview",
            new StringContent(json, Encoding.UTF8, "application/json"));
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        var root = doc.RootElement;
        Assert.Equal("Aster Office Supplies", root.GetProperty("customerName").GetString());
        Assert.Equal("A",    root.GetProperty("tier").GetString());
        Assert.Equal("9.50", root.GetProperty("subtotal").GetString());
        Assert.Equal("0.86", root.GetProperty("gst").GetString());
        Assert.Equal("10.36", root.GetProperty("total").GetString());
    }

    [Fact]
    public async Task Preview_UnknownCustomerId_Returns404()
    {
        var body = new
        {
            customerId = 999,
            lines = new[] { new { productCode = "PAPER-A4", qty = 1, unitPrice = "10.00" } }
        };
        var status = await PostPreviewStatus(body);
        Assert.Equal(HttpStatusCode.NotFound, status);
    }

    [Fact]
    public async Task Preview_UnknownProductCode_Returns404()
    {
        var body = new
        {
            customerId = 1,
            lines = new[] { new { productCode = "UNKNOWN", qty = 1, unitPrice = "10.00" } }
        };
        var status = await PostPreviewStatus(body);
        Assert.Equal(HttpStatusCode.NotFound, status);
    }

    // ── Exact response fields ─────────────────────────────────────────────────

    [Fact]
    public async Task Preview_ResponseContainsExactTopLevelFields()
    {
        var body = new
        {
            customerId = 1,
            lines = new[] { new { productCode = "PAPER-A4", qty = 1, unitPrice = "10.00" } }
        };
        var result = await PostPreview(body);

        Assert.True(result.TryGetProperty("customerId",   out _));
        Assert.True(result.TryGetProperty("customerName", out _));
        Assert.True(result.TryGetProperty("tier",         out _));
        Assert.True(result.TryGetProperty("subtotal",     out _));
        Assert.True(result.TryGetProperty("gst",          out _));
        Assert.True(result.TryGetProperty("total",        out _));
        Assert.True(result.TryGetProperty("lines",        out _));
    }

    [Fact]
    public async Task Preview_CustomerNameAndTierMatchCatalog()
    {
        var body = new
        {
            customerId = 2,
            lines = new[] { new { productCode = "PAPER-A4", qty = 1, unitPrice = "10.00" } }
        };
        var result = await PostPreview(body);

        Assert.Equal("Merlion Retail", result.GetProperty("customerName").GetString());
        Assert.Equal("B",              result.GetProperty("tier").GetString());
    }

    [Fact]
    public async Task Preview_ResponseContainsExactLineFields()
    {
        var body = new
        {
            customerId = 1,
            lines = new[] { new { productCode = "PAPER-A4", qty = 1, unitPrice = "10.00" } }
        };
        var result = await PostPreview(body);

        var line = result.GetProperty("lines")[0];
        Assert.True(line.TryGetProperty("lineNo",      out _));
        Assert.True(line.TryGetProperty("productCode", out _));
        Assert.True(line.TryGetProperty("qty",         out _));
        Assert.True(line.TryGetProperty("unitPrice",   out _));
        Assert.True(line.TryGetProperty("lineNet",     out _));
    }

    [Fact]
    public async Task Preview_MoneyValuesAreFixedTwoDecimalStrings()
    {
        var body = new
        {
            customerId = 1,
            lines = new[] { new { productCode = "PAPER-A4", qty = 1, unitPrice = "10.00" } }
        };
        var result = await PostPreview(body);

        AssertIsTwoDecimalString(result.GetProperty("subtotal"));
        AssertIsTwoDecimalString(result.GetProperty("gst"));
        AssertIsTwoDecimalString(result.GetProperty("total"));
        AssertIsTwoDecimalString(result.GetProperty("lines")[0].GetProperty("lineNet"));
    }

    // ── Validation: 400 cases ─────────────────────────────────────────────────

    [Fact]
    public async Task Preview_MissingCustomerId_Returns400()
    {
        var body = new
        {
            lines = new[] { new { productCode = "PAPER-A4", qty = 1, unitPrice = "10.00" } }
        };
        var status = await PostPreviewStatus(body);
        Assert.Equal(HttpStatusCode.BadRequest, status);
    }

    [Fact]
    public async Task Preview_MissingLines_Returns400()
    {
        var status = await PostPreviewStatus(new { customerId = 1 });
        Assert.Equal(HttpStatusCode.BadRequest, status);
    }

    [Fact]
    public async Task Preview_EmptyLines_Returns400()
    {
        var status = await PostPreviewStatus(new { customerId = 1, lines = Array.Empty<object>() });
        Assert.Equal(HttpStatusCode.BadRequest, status);
    }

    [Fact]
    public async Task Preview_QtyZero_Returns400()
    {
        var body = new
        {
            customerId = 1,
            lines = new[] { new { productCode = "PAPER-A4", qty = 0, unitPrice = "10.00" } }
        };
        var status = await PostPreviewStatus(body);
        Assert.Equal(HttpStatusCode.BadRequest, status);
    }

    [Fact]
    public async Task Preview_QtyString_Returns400()
    {
        // qty as a JSON string value — must be rejected
        const string json = """{"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":"100","unitPrice":"10.00"}]}""";
        var status = await PostPreviewRaw(json);
        Assert.Equal(HttpStatusCode.BadRequest, status);
    }

    [Fact]
    public async Task Preview_QtyFractional_Returns400()
    {
        // qty as a JSON fractional number — must be rejected
        const string json = """{"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":1.5,"unitPrice":"10.00"}]}""";
        var status = await PostPreviewRaw(json);
        Assert.Equal(HttpStatusCode.BadRequest, status);
    }

    [Fact]
    public async Task Preview_MalformedJson_Returns400()
    {
        var status = await PostPreviewRaw("{not valid json}");
        Assert.Equal(HttpStatusCode.BadRequest, status);
    }

    [Fact]
    public async Task Preview_InvalidUnitPrice_Returns400()
    {
        var body = new
        {
            customerId = 1,
            lines = new[] { new { productCode = "PAPER-A4", qty = 1, unitPrice = "abc" } }
        };
        var status = await PostPreviewStatus(body);
        Assert.Equal(HttpStatusCode.BadRequest, status);
    }

    [Fact]
    public async Task Preview_NonPositiveUnitPrice_Returns400()
    {
        var body = new
        {
            customerId = 1,
            lines = new[] { new { productCode = "PAPER-A4", qty = 1, unitPrice = "0.00" } }
        };
        var status = await PostPreviewStatus(body);
        Assert.Equal(HttpStatusCode.BadRequest, status);
    }

    // ── Write route rejection ─────────────────────────────────────────────────

    [Fact]
    public async Task Put_InvoicePreview_IsRejected()
    {
        var response = await _client.PutAsync("/api/invoice-preview",
            new StringContent("{}", Encoding.UTF8, "application/json"));
        Assert.True((int)response.StatusCode >= 400 && (int)response.StatusCode < 600);
    }

    [Fact]
    public async Task Delete_InvoicePreview_IsRejected()
    {
        var response = await _client.DeleteAsync("/api/invoice-preview");
        Assert.True((int)response.StatusCode >= 400 && (int)response.StatusCode < 600);
    }

    [Fact]
    public async Task Post_UndeclaredRoute_IsRejected()
    {
        var response = await _client.PostAsync("/api/other",
            new StringContent("{}", Encoding.UTF8, "application/json"));
        Assert.True((int)response.StatusCode >= 400 && (int)response.StatusCode < 600);
    }

    // ── Zero writes ───────────────────────────────────────────────────────────

    [Fact]
    public async Task Preview_NeverIncrementsWriteCount()
    {
        var body = new
        {
            customerId = 1,
            lines = new[] { new { productCode = "PAPER-A4", qty = 1, unitPrice = "10.00" } }
        };

        for (int i = 0; i < 3; i++)
            await PostPreview(body);

        var healthResponse = await _client.GetAsync("/internal/health");
        var doc = JsonDocument.Parse(await healthResponse.Content.ReadAsStringAsync());
        Assert.Equal(0, doc.RootElement.GetProperty("writeCount").GetInt32());
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private async Task<JsonElement> PostPreview(object body)
    {
        var response = await _client.PostAsJsonAsync("/api/invoice-preview", body);
        response.EnsureSuccessStatusCode();
        var json = await response.Content.ReadAsStringAsync();
        return JsonDocument.Parse(json).RootElement;
    }

    private async Task<HttpStatusCode> PostPreviewStatus(object body)
    {
        var response = await _client.PostAsJsonAsync("/api/invoice-preview", body);
        return response.StatusCode;
    }

    private async Task<HttpStatusCode> PostPreviewRaw(string json)
    {
        var content = new StringContent(json, Encoding.UTF8, "application/json");
        var response = await _client.PostAsync("/api/invoice-preview", content);
        return response.StatusCode;
    }

    private static void AssertIsTwoDecimalString(JsonElement element)
    {
        Assert.Equal(JsonValueKind.String, element.ValueKind);
        var s = element.GetString()!;
        var dotIndex = s.IndexOf('.');
        Assert.True(dotIndex >= 0, $"Expected decimal point in '{s}'");
        Assert.Equal(2, s.Length - dotIndex - 1);
    }
}
