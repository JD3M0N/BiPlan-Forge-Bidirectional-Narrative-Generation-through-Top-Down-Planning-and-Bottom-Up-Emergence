import { ApiError, apiRequest } from "./api";


describe("apiRequest", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("returns parsed JSON responses", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ id: "story-1" }),
    });

    await expect(apiRequest<{ id: string }>("/stories")).resolves.toEqual({ id: "story-1" });
    expect(global.fetch).toHaveBeenCalledWith("http://localhost:8000/stories", expect.any(Object));
  });

  it("returns undefined for 204 responses", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: vi.fn(),
    });

    await expect(apiRequest<void>("/auth/logout", { method: "POST" })).resolves.toBeUndefined();
  });

  it("uses API detail when available", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: vi.fn().mockResolvedValue({ detail: "Invalid credentials" }),
    });

    await expect(apiRequest("/auth/login")).rejects.toEqual(new ApiError("Invalid credentials", 401));
  });

  it("formats FastAPI validation detail arrays", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: vi.fn().mockResolvedValue({
        detail: [
          {
            loc: ["body", "characters", 0, "name"],
            msg: "Field required",
            type: "missing",
          },
          {
            loc: ["body", "plot"],
            msg: "String should have at least 12 characters",
            type: "string_too_short",
          },
        ],
      }),
    });

    await expect(apiRequest("/stories/generate")).rejects.toEqual(
      new ApiError(
        "characters.0.name: Field required; plot: String should have at least 12 characters",
        422,
      ),
    );
  });

  it("formats object details instead of rendering object Object", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: vi.fn().mockResolvedValue({ detail: { message: "Gemini rejected the request" } }),
    });

    await expect(apiRequest("/stories/generate")).rejects.toEqual(
      new ApiError("Gemini rejected the request", 500),
    );
  });

  it("falls back to a generic message when error JSON cannot be parsed", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: vi.fn().mockRejectedValue(new Error("invalid json")),
    });

    await expect(apiRequest("/stories")).rejects.toEqual(new ApiError("Request failed", 500));
  });
});
