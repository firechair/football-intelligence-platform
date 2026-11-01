import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const limit = searchParams.get('limit') || '50';
    const offset = searchParams.get('offset') || '0';

    // Build backend URL
    const backendUrl = process.env.INGESTION_URL || 'http://localhost:8001';
    const endpoint = `${backendUrl}/api/v1/accuracy/results?limit=${limit}&offset=${offset}`;


    console.log(`[ACCURACY RESULTS API] Calling backend: ${endpoint}`);

    const response = await fetch(endpoint, {
      method: 'GET',
      cache: 'no-store',
      headers: {
        'Content-Type': 'application/json',
      },
      signal: AbortSignal.timeout(30000), // 30 seconds timeout
    });

    if (!response.ok) {
      console.error(`[ACCURACY RESULTS API] Backend responded with status: ${response.status}`);
      return NextResponse.json({
        success: false,
        error: `Backend responded with status: ${response.status}`
      }, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);

  } catch (error) {
    console.error('[ACCURACY RESULTS API] Error:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Errore nel recupero dei risultati di accuratezza',
        details: error instanceof Error ? error.message : 'Errore sconosciuto'
      },
      { status: 500 }
    );
  }
}
