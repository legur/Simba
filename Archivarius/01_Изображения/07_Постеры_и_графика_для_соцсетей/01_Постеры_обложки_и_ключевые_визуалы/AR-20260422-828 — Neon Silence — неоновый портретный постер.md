---
id: AR-20260422-828
title: prompts.chat — Neon Silence
type: prompt
format: structured_prompt
primary_category: 01_Изображения
subcategory: 07_Постеры_и_соцграфика
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
- structured_prompt
- general
- prompt-type-structured
- contributor-kyllimirr-gmail-com
source: f/prompts.chat
source_url: https://github.com/f/prompts.chat
contributor: kyllimirr@gmail.com
for_devs: false
routing_confidence: 0.82
routing_method: image-body-poster
source_batch: prompts_chat_sort_20260422
related_to: []
canonical_id: null
---

## Назначение
Промт для постера или инфографики «Neon Silence». Нужен, когда требуется создать постер или ключевой визуал под тему.
## Исходный промпт
````text
{
  "task": "style_transfer_portrait_poster",
  "input": {
    "reference_image": "${reference_image_url_or_path}",
    "use_reference_as": "content_and_pose",
    "preserve": [
      "yüz ifadesi ve bakış yönü",
      "saç/siluet ve kıyafet formu",
      "kadraj (üst gövde portre)",
      "ışık yönü ve gölge dağılımı"
    ]
  },
  "prompt": {
    "language": "tr",
    "style_goal": "Referans görseldeki kişiyi/konuyu, aynı kompozisyonu koruyarak yüksek kontrastlı neon-ink poster illüstrasyonu stiline dönüştür.",
    "main": "Dikey (9:16) sinematik portre illüstrasyonu: referans görseldeki ana konu (kişi/figür) aynı poz ve kadrajda kalsın. Stil: koyu lacivert/siyah mürekkep dokuları ve kalın konturlar; yüz ve kıyafet üzerinde oyma/gravür benzeri ince çizgisel gölgelendirme (etched shading), cel-shading ile birleşen poster estetiği. Arka plan: düz, çok doygun sıcak neon pembe/kırmızı zemin; etrafında sıvı mürekkep/duman girdapları, akışkan alevimsi kıvrımlar ve parçacık sıçramaları. Vurgu rengi olarak neon pembe/kırmızı lekeler: yüzde çizik/iz gibi küçük vurgular, giyside ve duman dokusunda serpiştirilmiş parlak damlacıklar. Yüksek kontrast, sert kenarlar, dramatik karanlık tonlar, minimal ama güçlü renk paleti (koyu soğuk tonlar + neon sıcak arka plan). Hafif baskı grain’i ve poster dokusu; ultra net, yüksek çözünürlüklü kapak/poster görünümü.",
    "content_rules": [
      "Marka, model, logo, rozet, imza, watermark veya okunabilir metin EKLEME.",
      "Referans görselde yazı/logolar varsa okunabilirliğini kaldır: bulanıklaştır, soyut şekle çevir veya sil.",
      "Yeni kişi/obje ekleme; sadece referanstaki içeriği stilize et.",
      "Yüz anatomi oranlarını bozma; doğal ama stilize kalsın."
    ]
  },
  "negative_prompt": [
    "photorealistic",
    "lowres",
    "blurry",
    "muddy shading",
    "extra people",
    "extra limbs",
    "deformed face",
    "uncanny",
    "new text",
    "brand names",
    "logos",
    "watermark",
    "signature",
    "busy background details",
    "washed out neon",
    "color banding",
    "jpeg artifacts"
  ],
  "generation": {
    "mode": "image_to_image",
    "strength": 0.6,
    "style_transfer_weight": 0.85,
    "composition_lock": 0.8,
    "detail_level": "high",
    "resolution": {
      "width": 1080,
      "height": 1920
    },
    "guidance": {
      "cfg_scale": 7.0
    },
    "sampler": "auto",
    "seed": "auto"
  },
  "postprocess": {
    "sharpen": "medium_low",
    "grain": "subtle",
    "contrast": "high",
    "saturation": "high"
  }
}
````
