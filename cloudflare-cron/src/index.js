/**
 * Cloudflare Cron Worker — 단일 스케줄 트리거
 * 봉 완성 주기: 1분(뉴스/AI채팅), 5분(지표/실적/캘린더), 매일 08:00 KST(인베스팅 실적)
 * BACKEND_URL, CRON_SECRET 은 Worker Secrets로 설정
 */

async function callCronEndpoint(backendUrl, secret, job) {
  const url = `${backendUrl.replace(/\/$/, '')}/api/cron/${job}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${secret}`,
      'Content-Type': 'application/json',
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${job} ${res.status}: ${text}`);
  }
  return res.json();
}

export default {
  async scheduled(controller, env, ctx) {
    const backendUrl = env.BACKEND_URL;
    const secret = env.CRON_SECRET;
    if (!backendUrl || !secret) {
      console.error('BACKEND_URL or CRON_SECRET not set');
      return;
    }

    const now = new Date();
    const utcMin = now.getUTCMinutes();
    const utcHour = now.getUTCHours();

    // 매 분: 뉴스 (봉 완성 1분 주기)
    ctx.waitUntil(
      callCronEndpoint(backendUrl, secret, 'news').then(() => console.log('cron/news ok')).catch(e => console.error('cron/news', e))
    );

    // 매 5분: 지표 / 실적 / 캘린더 (봉 완성 5분 주기)
    if (utcMin % 5 === 0) {
      ctx.waitUntil(
        callCronEndpoint(backendUrl, secret, 'indicators').then(() => console.log('cron/indicators ok')).catch(e => console.error('cron/indicators', e))
      );
      ctx.waitUntil(
        callCronEndpoint(backendUrl, secret, 'earnings').then(() => console.log('cron/earnings ok')).catch(e => console.error('cron/earnings', e))
      );
      ctx.waitUntil(
        callCronEndpoint(backendUrl, secret, 'calendar').then(() => console.log('cron/calendar ok')).catch(e => console.error('cron/calendar', e))
      );
    }

    // 매일 23:00 UTC = 08:00 KST: 인베스팅 오늘의 실적
    if (utcHour === 23 && utcMin === 0) {
      ctx.waitUntil(
        callCronEndpoint(backendUrl, secret, 'investing-earnings').then(() => console.log('cron/investing-earnings ok')).catch(e => console.error('cron/investing-earnings', e))
      );
    }

    // 매 2분: AI 랜덤 채팅 (단일 실행)
    if (utcMin % 2 === 0) {
      ctx.waitUntil(
        callCronEndpoint(backendUrl, secret, 'ai-chat').then(() => console.log('cron/ai-chat ok')).catch(e => console.error('cron/ai-chat', e))
      );
    }
  },
};
