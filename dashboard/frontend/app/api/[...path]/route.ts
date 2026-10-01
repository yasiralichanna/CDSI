import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
    const params = await context.params;
    return handleProxy(request, params);
}

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
    const params = await context.params;
    return handleProxy(request, params);
}

export async function PUT(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
    const params = await context.params;
    return handleProxy(request, params);
}

export async function DELETE(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
    const params = await context.params;
    return handleProxy(request, params);
}

async function handleProxy(request: NextRequest, params: { path: string[] }) {
    const pathStr = params.path ? params.path.join("/") : "";
    const backendBase = (process.env.NEXT_PUBLIC_API_URL || process.env.BACKEND_URL || "https://cdsi-backend.onrender.com").replace(/\/+$/, "");
    const targetUrl = `${backendBase}/api/${pathStr}${request.nextUrl.search}`;

    try {
        const body = (request.method !== "GET" && request.method !== "HEAD") ? await request.text() : undefined;
        
        const res = await fetch(targetUrl, {
            method: request.method,
            headers: {
                "Content-Type": request.headers.get("content-type") || "application/json",
                "Accept": "application/json",
            },
            body: body,
        });

        const data = await res.text();
        return new NextResponse(data, {
            status: res.status,
            headers: {
                "Content-Type": res.headers.get("content-type") || "application/json",
            },
        });
    } catch (err: any) {
        return NextResponse.json(
            { error: `Failed to proxy request to backend: ${err?.message || err}` },
            { status: 502 }
        );
    }
}
