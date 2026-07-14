import { NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  { params }: { params: { run_id: string } },
) {
  // Polling gets a slimmed payload by default; ?full=true forwards to the
  // backend for the complete evidence (scraped page content, chunk text).
  const full = new URL(request.url).searchParams.get("full");
  const qs = full ? `?full=${full}` : "";
  try {
    const res = await fetch(`${BACKEND}/api/run/${params.run_id}${qs}`, {
      cache: "no-store",
    });
    if (res.status === 404) {
      return NextResponse.json({ error: "run not found" }, { status: 404 });
    }
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    return NextResponse.json(
      { error: `Backend unreachable: ${(err as Error).message}` },
      { status: 502 },
    );
  }
}

export async function DELETE(
  _request: Request,
  { params }: { params: { run_id: string } },
) {
  try {
    const res = await fetch(`${BACKEND}/api/run/${params.run_id}`, {
      method: "DELETE",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    return NextResponse.json(
      { error: `Backend unreachable: ${(err as Error).message}` },
      { status: 502 },
    );
  }
}
