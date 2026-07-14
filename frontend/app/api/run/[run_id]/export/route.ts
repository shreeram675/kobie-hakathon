import { NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  { params }: { params: { run_id: string } },
) {
  const download = new URL(request.url).searchParams.get("download");
  const qs = download ? `?download=${download}` : "";

  try {
    const res = await fetch(
      `${BACKEND}/api/run/${params.run_id}/export${qs}`,
      { cache: "no-store" },
    );
    if (res.status === 404) {
      return NextResponse.json({ error: "run not found" }, { status: 404 });
    }

    if (download) {
      const body = await res.arrayBuffer();
      const headers = new Headers({
        "content-type": res.headers.get("content-type") ?? "application/json",
      });
      const disposition = res.headers.get("content-disposition");
      if (disposition) headers.set("content-disposition", disposition);
      return new NextResponse(body, { status: res.status, headers });
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
