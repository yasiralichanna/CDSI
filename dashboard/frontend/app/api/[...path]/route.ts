import { NextRequest, NextResponse } from "next/server";

async function getParams(context: any): Promise<{ path: string[] }> {
    if (!context || !context.params) return { path: [] };
    if (typeof context.params.then === "function") {
        return await context.params;
    }
    return context.params;
}

export async function GET(request: NextRequest, context: any) {
    const params = await getParams(context);
    return handleProxy(request, params);
}

export async function POST(request: NextRequest, context: any) {
    const params = await getParams(context);
    return handleProxy(request, params);
}

export async function PUT(request: NextRequest, context: any) {
    const params = await getParams(context);
    return handleProxy(request, params);
}

export async function DELETE(request: NextRequest, context: any) {
    const params = await getParams(context);
    return handleProxy(request, params);
}

async function handleProxy(request: NextRequest, params: { path: string[] }) {
    const pathSegments = params?.path || [];
    const pathStr = Array.isArray(pathSegments) ? pathSegments.join("/") : "";
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
            cache: "no-store",
        });

        const data = await res.text();
        return new NextResponse(data, {
            status: res.status,
            headers: {
                "Content-Type": res.headers.get("content-type") || "application/json",
                "Cache-Control": "no-store, max-age=0",
            },
        });
    } catch (err: any) {
        return NextResponse.json(
            { error: `Failed to proxy request to backend: ${err?.message || err}` },
            { status: 502 }
        );
    }
}

