# دليل التثبيت

## 1. البوت (Termux)
    cd ~/child-tracker
    bash bot/setup.sh
    nano bot/.env    # املأ القيم
    bash bot/run.sh

## 2. تطبيق الطفل
- يُبنى تلقائياً عبر GitHub Actions.
- حمّل الـ APK من تبويب Actions → Artifacts.

## 3. Supabase
- أنشئ مشروعاً على https://supabase.com
- أنشئ جدول locations بالحقول:
  - id (uuid, primary key, default gen_random_uuid())
  - device_id (text)
  - latitude (float8)
  - longitude (float8)
  - altitude (float8, nullable)
  - speed (float8, nullable)
  - accuracy (float8, nullable)
  - heading (float8, nullable)
  - timestamp (timestamptz)
  - battery (int, nullable)
