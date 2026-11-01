import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const base = process.env.HOICO_API_URL || "http://localhost:8000";
  try {
    const body = await request.text();
    const response = await fetch(`${base}/api/scenarios/compare`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      cache: "no-store",
    });
    const text = await response.text();
    return new NextResponse(text, {
      status: response.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return NextResponse.json(
      { detail: "The local API is not reachable from this console." },
      { status: 503 },
    );
  }
}
