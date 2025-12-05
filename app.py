# ---------------------------
# CRON (FINAL - UTC BAZLI)
# ---------------------------
@app.route("/cron", methods=["GET", "HEAD"])
def cron():
    key = request.args.get("key")
    if key != Config.CRON_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    
    # ✅ UTC saati al (Render UTC'de çalışıyor)
    now_utc = datetime.now(pytz.UTC)
    hour_utc = now_utc.hour
    
    # Türkiye saati sadece log için
    tz_tr = pytz.timezone(Config.TIMEZONE)
    now_tr = now_utc.astimezone(tz_tr)
    
    logger.info(f"⏰ /cron tetiklendi (UTC: {hour_utc:02d}:{now_utc.minute:02d}, TR: {now_tr.strftime('%H:%M')})")
    
    results = []
    
    # ✅ SABAH 05:00-05:59 UTC = TR 08:00-08:59
    if 5 <= hour_utc < 6:
        logger.info("▶️ morning çalıştırılıyor...")
        try:
            result = morning_job()
            if not result or not result.get("skipped"):
                results.append("morning ✅")
            else:
                results.append("morning ⏭️ (atlandı)")
        except Exception as e:
            logger.exception(f"❌ morning_job hatası: {e}")
            results.append(f"morning ❌ {str(e)}")
    
    # ✅ ÖĞLE 09:00-09:59 UTC = TR 12:00-12:59
    elif 9 <= hour_utc < 10:
        logger.info("▶️ noon çalıştırılıyor...")
        try:
            result = noon_job()
            if not result or not result.get("skipped"):
                results.append("noon ✅")
            else:
                results.append("noon ⏭️ (atlandı)")
        except Exception as e:
            logger.exception(f"❌ noon_job hatası: {e}")
            results.append(f"noon ❌ {str(e)}")
    
    # ✅ AKŞAM 15:00-15:59 UTC = TR 18:00-18:59
    elif 15 <= hour_utc < 16:
        logger.info("▶️ evening çalıştırılıyor...")
        try:
            result = evening_job()
            if not result or not result.get("skipped"):
                results.append("evening ✅")
            else:
                results.append("evening ⏭️ (atlandı)")
        except Exception as e:
            logger.exception(f"❌ evening_job hatası: {e}")
            results.append(f"evening ❌ {str(e)}")
    
    # ✅ GECE 20:00-20:59 UTC = TR 23:00-23:59
    elif 20 <= hour_utc < 21:
        logger.info("▶️ night çalıştırılıyor...")
        try:
            result = night_job()
            if not result or not result.get("skipped"):
                results.append("night ✅")
            else:
                results.append("night ⏭️ (atlandı)")
        except Exception as e:
            logger.exception(f"❌ night_job hatası: {e}")
            results.append(f"night ❌ {str(e)}")
    
    # ✅ TEMİZLİK 00:00-00:59 UTC = TR 03:00-03:59
    elif hour_utc == 0:
        logger.info("▶️ cleanup çalıştırılıyor...")
        try:
            result = cleanup_job()
            if not result or not result.get("skipped"):
                results.append("cleanup ✅")
            else:
                results.append("cleanup ⏭️ (atlandı)")
        except Exception as e:
            logger.exception(f"❌ cleanup_job hatası: {e}")
            results.append(f"cleanup ❌ {str(e)}")
    
    # DİĞER SAATLER
    else:
        results.append(f"⏸️  UTC {hour_utc:02d}:xx (TR {now_tr.hour:02d}:xx) - Planlanmış görev yok")
    
    return jsonify({
        "status": "ok",
        "timestamp": now_utc.isoformat(),
        "hour_utc": hour_utc,
        "hour_tr": now_tr.hour,
        "results": results
    }), 200
