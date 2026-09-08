<template>
  <div class="landing-page">
    <header class="topbar">
      <div class="brand">
        <img :src="CareerPulseLogo" alt="CareerPulse" class="brand-logo">
      </div>


      <div class="auth-links">
        <router-link :to="{ path: '/login', query: { force: '1' } }" class="signup-btn">登录</router-link>
      </div>
    </header>

    <main class="hero-wrap">
      <section class="hero-copy">
        <span class="badge">AI 职业导航与成长陪伴</span>
        <h1>
          CareerPulse<br />
          重塑您的职业未来
        </h1>
        <p>
          整合个人背景、岗位要求与能力差距，帮助您梳理职业方向，
          形成从职业探索到成长计划的连续导航体验。
        </p>

        <div class="hero-actions">
          <router-link :to="{ path: '/login', query: { force: '1' } }" class="start-btn">开始分析</router-link>
        </div>

        <div class="social-proof">
          <p>以真实画像、岗位数据和成长记录支持持续职业决策</p>
        </div>
      </section>

      <section class="hero-visual" aria-label="career visual card">
        <img :src="Airi" alt="AI Career Roadmap" class="airi-image">
      </section>
    </main>

    <section class="metrics">
      <article>
        <h3>职业探索</h3>
        <p>了解岗位方向与能力要求</p>
      </article>
      <article>
        <h3>能力分析</h3>
        <p>识别人岗匹配与技能差距</p>
      </article>
      <article>
        <h3>成长规划</h3>
        <p>围绕目标形成行动计划</p>
      </article>
      <article>
        <h3>持续记录</h3>
        <p>沉淀分析与成长过程</p>
      </article>
    </section>
  </div>
</template>

<script setup lang="ts">
import Airi from '@/assets/airi.png'
import CareerPulseLogo from '@/assets/logoo.png'
</script>

<style scoped>
.landing-page {
  min-height: 100vh;
  background: linear-gradient(90deg, #edf8ff 0%, #f8f0ff 100%);
  color: #1f2b46;
}

.topbar {
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 42px;
  background: #ffffff;
  border-bottom: 1px solid #e5ebf6;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.brand-logo {
  height: 320px;
  width: auto;
  display: block;
}

.nav-links {
  display: inline-flex;
  gap: 34px;
}

.nav-links a {
  color: #2c3650;
  text-decoration: none;
  font-size: 15px;
  font-weight: 600;
}

.auth-links {
  display: inline-flex;
  align-items: center;
  gap: 14px;
}


.signup-btn {
  text-decoration: none;
  color: #fff;
  font-weight: 700;
  padding: 10px 20px;
  border-radius: 999px;
  background: linear-gradient(135deg, #2f7bff 0%, #3255e8 100%);
  box-shadow: 0 8px 18px rgba(53, 97, 238, 0.25);
}

.hero-wrap {
  max-width: 1240px;
  margin: 0 auto;
  padding: 60px 26px 24px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(460px, 0.9fr);
  gap: 34px;
  align-items: center;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  padding: 8px 14px;
  font-size: 13px;
  color: #3270c3;
  background: #edf4ff;
  border: 1px solid #dce8fa;
}

.hero-copy h1 {
  margin: 18px 0 16px;
  line-height: 1.14;
  font-size: 64px;
  color: #0f1731;
}

.hero-copy h1 span {
  color: #5347e8;
}

.hero-copy p {
  margin: 0;
  font-size: 27px;
  line-height: 1.75;
  color: #4f5d78;
  max-width: 680px;
}

.hero-actions {
  margin-top: 30px;
}

.start-btn {
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 16px 34px;
  border-radius: 14px;
  color: #ffffff;
  font-size: 31px;
  font-weight: 700;
  background: linear-gradient(135deg, #15a4ff 0%, #2f64ff 100%);
  box-shadow: 0 12px 28px rgba(32, 107, 246, 0.28);
}

.social-proof {
  margin-top: 24px;
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.avatars {
  display: inline-flex;
}

.avatars span {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  margin-right: -8px;
  border: 2px solid #ffffff;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #3f76ff 0%, #8b58ee 100%);
}

.social-proof p {
  margin: 0;
  font-size: 15px;
  color: #4a5670;
}

.hero-visual {
  min-height: 520px;
  border-radius: 24px;
  position: relative;
  padding: 30px;
  overflow: hidden;
  background: radial-gradient(circle at 16% 18%, #5f77ff 0%, #4d48e6 38%, #2d2b9c 100%);
  box-shadow: 0 28px 60px rgba(91, 79, 224, 0.28);
}

.airi-image {
  width: min(86%, 430px);
  max-height: 460px;
  height: auto;
  object-fit: contain;
  display: block;
  margin: 0 auto;
}

.visual-head {
  color: #f4f7ff;
  font-size: 32px;
  font-weight: 700;
  margin-bottom: 18px;
}

.roadmap-list {
  display: grid;
  gap: 10px;
  max-width: 56%;
}

.roadmap-list span {
  color: rgba(255, 255, 255, 0.9);
  font-size: 19px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  background: rgba(255, 255, 255, 0.08);
}

.person-shape {
  position: absolute;
  right: -22px;
  bottom: -18px;
  width: 360px;
  height: 500px;
  border-radius: 220px 220px 24px 24px;
  background: linear-gradient(160deg, rgba(28, 39, 114, 0.9), rgba(12, 14, 48, 0.96));
  box-shadow: inset 0 0 0 2px rgba(255, 255, 255, 0.12);
}

.metrics {
  max-width: 1240px;
  margin: 18px auto 0;
  padding: 0 26px 40px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
}

.metrics article {
  background: #fff;
  border: 1px solid #e5e9f2;
  padding: 22px 16px;
  text-align: center;
}

.metrics article + article {
  border-left: 0;
}

.metrics h3 {
  margin: 0;
  font-size: 27px;
}

.metrics p {
  margin: 6px 0 0;
  color: #69748a;
  font-size: 14px;
}

@media (max-width: 1100px) {
  .topbar {
    padding: 0 18px;
  }

  .nav-links {
    display: none;
  }

  .hero-wrap {
    grid-template-columns: 1fr;
    padding-top: 30px;
  }

  .airi-image {
    width: min(80%, 340px);
    max-height: 360px;
  }

  .hero-copy h1 {
    font-size: 46px;
  }

  .hero-copy p {
    font-size: 18px;
  }

  .start-btn {
    font-size: 20px;
  }

  .metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }

  .metrics article + article {
    border-left: 1px solid #e5e9f2;
  }
}

@media (max-width: 767px) {
  .topbar {
    height: 64px;
    padding: 0 14px;
  }

  .brand-logo {
    height: 220px;
    max-width: 210px;
    object-fit: contain;
  }

  .signup-btn {
    padding: 8px 16px;
    font-size: 14px;
  }

  .hero-wrap {
    padding: 28px 16px 16px;
    gap: 20px;
  }

  .badge {
    padding: 7px 11px;
    font-size: 12px;
  }

  .hero-copy h1 {
    margin: 16px 0 12px;
    font-size: clamp(34px, 10.5vw, 42px);
  }

  .hero-copy p {
    font-size: 16px;
    line-height: 1.65;
  }

  .hero-actions {
    margin-top: 22px;
  }

  .start-btn {
    width: min(100%, 280px);
    padding: 13px 24px;
    font-size: 18px;
  }

  .social-proof {
    display: block;
    margin-top: 18px;
  }

  .social-proof p {
    line-height: 1.6;
  }

  .hero-visual {
    min-height: 320px;
    padding: 16px;
    border-radius: 20px;
  }

  .airi-image {
    width: min(90%, 300px);
    max-height: 300px;
  }

  .metrics {
    margin-top: 10px;
    padding: 0 16px 28px;
    gap: 8px;
  }

  .metrics article {
    min-width: 0;
    padding: 16px 10px;
  }

  .metrics h3 {
    font-size: 20px;
  }

  .metrics p {
    overflow-wrap: anywhere;
    font-size: 13px;
  }
}

@media (max-width: 320px) {
  .hero-wrap,
  .metrics {
    padding-left: 12px;
    padding-right: 12px;
  }

  .hero-visual {
    min-height: 286px;
  }
}
</style>
