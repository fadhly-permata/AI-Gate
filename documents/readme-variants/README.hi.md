# aigate 🚪

aigate आपके सारे AI providers के लिए एक ही दरवाज़ा है। यहीं AI agents
आपके लिए कोड लिखते भी हैं। और यह पूरा काम आप अपने फ़ोन से भी कर सकते
हैं।

यह एक साधारण Python ऐप है — न Docker, न कोई cloud account। आपकी API keys
और पुरानी गतिविधियाँ बस आपके अपने डिवाइस में रहती हैं।

aigate मुफ़्त है और इसका कोड सबके लिए खुला है — कोई पेड प्लान नहीं, कोई फ़ीचर
लॉक नहीं। यह कोड कोई भी कॉपी कर सकता है, इसलिए aigate का एकमात्र आधिकारिक पता
यही है: [github.com/fadhly-permata/AI-Gate](https://github.com/fadhly-permata/AI-Gate)

🌐 [English](../../README.md) · [Bahasa Indonesia](README.id.md) · [Русский](README.ru.md) · [Nederlands](README.nl.md) · [日本語](README.ja.md) · [简体中文](README.zh.md) · [繁體中文](README.zh-tw.md) · **हिन्दी**

## रात की चाय ☕

खाना खत्म, मेज़ पर चाय रखी है। अचानक याद आया कि project का एक error
बहुत दिन से पड़ा है। फ़ोन उठाया, browser खोला, agent को एक लाइन में
बताया — और काम शुरू। terminal tab में साफ़ दिखता है कि वह एक-एक error
ठीक कर रहा है, टेस्ट दोबारा चला रहा है। सब साफ़ होते ही सारे fix अपने आप
main branch में पहुँच गए। चाय अब भी गुनगुनी है, और कोड ठीक हो चुका है।

## क्या इसे अलग बनाता है ✨

- **सारे AI providers, एक ही जगह से।** अपने provider accounts एक बार
  aigate से जोड़ दीजिए, फिर वह आपके requests खुद सही जगह भेजता है। कोई
  provider बंद हो या उसकी quota खत्म हो जाए, request अपने आप अगले
  provider पर चला जाता है।
- **24 AI coding tools, एक टैप में।** aigate इन्हें अपने built-in terminal
  tabs में ही चला देता है। कोई tool पहले से इंस्टॉल नहीं है? तो aigate
  वही install command दिखाता है जो आपके डिवाइस पर सच में चलेगी। यह list
  अभी भी बन रही है — आने वाले versions में tools जुड़ या बदल सकते हैं।
- **आपकी नज़र के सामने auto-fix।** aigate पहले एक branch बनाता है, फिर
  agent को एक ऐसे tab में चलाता है जिसे आप कभी भी खोलकर देख सकते हैं।
  एक-एक error ठीक होता है, टेस्ट पास होते हैं, फिर सब कुछ main branch में
  merge हो जाता है। काम पूरा न होने पर aigate कभी "हो गया" नहीं बोलता।
- **सच में फ़ोन पर चलता है।** Android पर aigate Termux में सीधे लगता है और
  चलता है — न compiler चाहिए, न build tools।
- **आपका डेटा, आपके पास।** API keys और request history आपके डिवाइस से
  बाहर नहीं जातीँ। internet पर सिर्फ़ वही request जाती हैं, जो आप अपने
  चुने हुए provider को भेजते हैं।
- **छोटी स्क्रीन पर भी आराम।** light और dark mode, सात भाषाएँ, और UI
  फ़ोन की छोटी स्क्रीन पर भी बिना झंझट चलता है।

## 60 सेकंड में आज़माएँ ⏱️

```bash
python run.py
```

फिर browser में **http://localhost:8080** खोलिए। पहली बार चलाने पर यह
खुद ही ज़रूरी Python packages डाउनलोड कर लेता है।

8080 port खाली नहीं है? तो यह इस्तेमाल कीजिए:

```bash
AIGATE_PORT=9090 python run.py
```

## फ़ोन पर चलाना 📱

Android पर aigate Termux में बिल्कुल laptop की तरह चलता है: चलाइए और
browser से खोलिए। असली चुनौती coding tools की होती है, क्योंकि Android
packages को laptop से अलग तरीके से इंस्टॉल करता है। aigate Termux को
पहचान लेता है, इसलिए जो install command दिखाता है वह आपके फ़ोन पर पक्का
चलेगा।

aigate Linux, Windows और Android (Termux) पर जाँचा जा चुका है — फ़ोन के
अंदर पूरा Linux distro चलाने में भी।

## पूरी तकनीकी बात wiki पर 📚

API, architecture, install तरीके और testing की पूरी जानकारी
[wiki](https://github.com/fadhly-permata/AI-Gate/wiki) पर है। यह README
बस परिचय तक सीमित है।

## हालत 📌

aigate एक निजी प्रोजेक्ट है जो लगातार बनता जा रहा है, और इसका सारा
डेटा आपके अपने डिवाइस में रहता है। यह Linux, Windows और Android (Termux)
पर जाँचा जा चुका है। बिना झिझक आज़माइए, तोड़िए-फोड़िए, और दिक्कत मिले तो
ज़रूर बताइए।

---

Fadhly Permata ने ❤️ के साथ इसे बनाया है
