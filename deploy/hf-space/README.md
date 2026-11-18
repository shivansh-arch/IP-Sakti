---
title: IP-SAKTI
emoji: 📜
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Prior-art search across Charaka Samhita and patents
---

# IP-SAKTI — prior-art search

Searches the Charaka Samhita (NIIMH e-Samhita) for passages that name the same plants and conditions as a herbal-medicine query or patent, and separately searches a sample of Indian patent filings (IPC A61K 36).

Results are research leads for a qualified examiner, not legal opinions. Source code, method and evaluation: https://github.com/shivansh-arch/IP-Sakti

This Space runs the FastAPI service and the web interface from one container. Vectors are stored in Qdrant Cloud and configured through the `QDRANT_URL` and `QDRANT_API_KEY` Space secrets.
