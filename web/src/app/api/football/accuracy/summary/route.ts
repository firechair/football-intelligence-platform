import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const days_back = searchParams.get('days_back') || '30';

    // Build backend URL
    const backendUrl = process.env.INGESTION_URL || 'http://localhost:8001';
    const endpoint = `${backendUrl}/api/v1/accuracy/statistics/summary?days_back=${days_back}`;


    console.log(`[ACCURACY SUMMARY API] Calling backend: ${endpoint}`);

    const response = await fetch(endpoint, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      signal: AbortSignal.timeout(30000), // 30 seconds timeout
    });

    if (!response.ok) {
      console.error(`[ACCURACY SUMMARY API] Backend responded with status: ${response.status}`);
      return NextResponse.json({
        success: false,
        error: `Backend responded with status: ${response.status}`
      }, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);

  } catch (error) {
    console.error('[ACCURACY SUMMARY API] Error:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Errore nel recupero delle statistiche di accuratezza',
        details: error instanceof Error ? error.message : 'Errore sconosciuto'
      },
      { status: 500 }
    );
  }
}
