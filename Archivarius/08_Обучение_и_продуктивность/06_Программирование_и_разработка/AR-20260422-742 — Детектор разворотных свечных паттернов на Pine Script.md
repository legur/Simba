---
id: AR-20260422-742
title: prompts.chat — Candlestick Reversal Pattern Detector in Pine Script
type: prompt
format: text_prompt
primary_category: 08_Обучение_и_productivity
subcategory: 06_Программирование_и_разработка
status: active
language: en
platform:
- prompts.chat
created: 2026-04-22
updated: '2026-04-22'
created_at: 2026-04-22
updated_at: '2026-04-22'
tags:
- prompts-chat
- github-import
- text_prompt
- general
- prompt-type-text
- contributor-cutejsq-gmail-com
source: f/prompts.chat
source_url: https://github.com/f/prompts.chat
contributor: cutejsq@gmail.com
for_devs: false
routing_confidence: 0.4
routing_method: fallback
source_batch: prompts_chat_sort_20260422
related_to: []
canonical_id: null
---


## Назначение
Промт для разработки или техразбора «Candlestick Reversal Pattern Detector in Pine Script». Нужен, когда требуется решить техническую задачу «Candlestick Reversal Pattern Detector in Pine Script».
## Исходный промпт
````text
Act as a TradingView Pine Script v5 developer. You are tasked with creating an indicator that automatically detects and plots candlestick reversal patterns on the price chart. 

Your task is to:
- Identify and label the following candlestick patterns:
  - Bullish: Morning Star, Hammer
  - Bearish: Evening Star, Bearish Engulfing
- For each detected pattern:
  - Plot a green upward arrow below the candle for bullish patterns with the text “BUY: Pattern Name”
  - Plot a red downward arrow above the candle for bearish patterns with the text “SELL: Pattern Name”
- Add optional trend confirmation using a moving average (user-selectable length).
  - Only show bullish signals above the MA and bearish signals below the MA (toggleable).
- Include an optional RSI panel:
  - RSI length input
  - Overbought and oversold levels
  - Allow RSI to be used as an additional filter for signals (on/off)
- Ensure the indicator overlays signals on the price chart and uses clear labels and arrows 
- Allow user inputs to enable/disable each candlestick pattern individually
- Make sure the script is clean, optimized, and fully compatible with TradingView.
````
