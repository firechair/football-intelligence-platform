import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const days_back = searchParams.get('days_back') || '30';
    const league_id = searchParams.get('league_id');

    // Build backend URL
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://example.invalid';
    let endpoint = `${backendUrl}/api/football/accuracy/summary?days_back=${days_back}`;

    if (league_id) {
      endpoint += `&league_id=${league_id}`;
    }

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
