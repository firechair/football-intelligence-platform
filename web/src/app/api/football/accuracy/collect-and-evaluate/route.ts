import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const days_back = searchParams.get('days_back') || '7';

    // Build backend URL
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://example.invalid';
    const endpoint = `${backendUrl}/api/football/accuracy/collect-and-evaluate?days_back=${days_back}`;

    console.log(`[ACCURACY EVALUATE API] Calling backend: ${endpoint}`);

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      signal: AbortSignal.timeout(120000), // 2 minutes timeout for evaluation
    });

    if (!response.ok) {
      console.error(`[ACCURACY EVALUATE API] Backend responded with status: ${response.status}`);
      return NextResponse.json({
        success: false,
        error: `Backend responded with status: ${response.status}`
      }, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);

  } catch (error) {
    console.error('[ACCURACY EVALUATE API] Error:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Errore nella valutazione dell\'accuratezza',
        details: error instanceof Error ? error.message : 'Errore sconosciuto'
      },
      { status: 500 }
    );
  }
}
