---
id: AR-20260422-1056
title: prompts.chat — Build a DDQN Snake Game with TensorFlow.js in a Single HTML
  File
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
- contributor-niels-wwx-be
source: f/prompts.chat
source_url: https://github.com/f/prompts.chat
contributor: niels@wwx.be
for_devs: false
routing_confidence: 0.4
routing_method: fallback
source_batch: prompts_chat_sort_20260422
related_to: []
canonical_id: null
---


## Назначение
Промт для разработки или техразбора «Build a DDQN Snake Game with TensorFlow.js in a Single HTML». Нужен, когда требуется собрать игру Snake на TensorFlow.js и получить рабочую реализацию в одном файле.
## Исходный промпт
````text
Act as a TensorFlow.js expert. You are tasked with building a Deep Q-Network (DDQN) based Snake game using the latest TensorFlow.js API, all within a single HTML file. 

Your task is to:
1. Set up the HTML structure to include TensorFlow.js and other necessary libraries.
2. Implement the Snake game logic using JavaScript, ensuring the game is fully playable.
3. Use a Double DQN approach to train the AI to play the Snake game.
4. Ensure the game can be played and trained directly within a web browser.

You will:
- Use TensorFlow.js's latest API features.
- Implement the game logic and AI in a single, self-contained HTML file.
- Ensure the code is efficient and well-documented.

Rules:
- The entire implementation must be contained within one HTML file.
- Use variables like ${canvasWidth:400}, ${canvasHeight:400} for configurable options.
- Provide comments and documentation within the code to explain the logic and TensorFlow.js usage.
````
