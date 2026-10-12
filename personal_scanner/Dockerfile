# Personal Scanner OCR server: the C++ engine plus a small HTTP API.
#
#   docker build -t personal-scanner .
#   docker run -p 8080:8080 -e PS_API_KEY=change-me personal-scanner

FROM ubuntu:24.04 AS build
RUN apt-get update && apt-get install -y --no-install-recommends \
      cmake g++ make libopencv-core-dev libopencv-imgproc-dev libopencv-imgcodecs-dev \
      libtesseract-dev libleptonica-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY CMakeLists.txt ./
COPY core core
COPY tools tools
COPY tests tests
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build -j"$(nproc)" \
    && ctest --test-dir build --output-on-failure

FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends \
      libopencv-core406t64 libopencv-imgproc406t64 libopencv-imgcodecs406t64 \
      libtesseract5 liblept5 tesseract-ocr-ben tesseract-ocr-eng \
      poppler-utils python3 python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY server/requirements.txt /app/requirements.txt
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r /app/requirements.txt
COPY --from=build /src/build/ps_ocr /usr/local/bin/ps_ocr
COPY server/app.py /app/app.py
RUN useradd --system --no-create-home scanner
USER scanner
WORKDIR /app
ENV PS_OCR_BIN=/usr/local/bin/ps_ocr OMP_THREAD_LIMIT=1
EXPOSE 8080
HEALTHCHECK CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=5)"
CMD ["/opt/venv/bin/uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
