FROM ubuntu:20.04

WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies for building linux-gpib (without kernel headers)
RUN apt-get update && apt-get install -y \
    build-essential automake autoconf libtool \
    libusb-dev python3-dev python3-pip \
    libreadline-dev flex bison wget unzip git

# Clone the latest linux-gpib source from SourceForge (via Git)
RUN git clone https://git.code.sf.net/p/linux-gpib/git linux-gpib-git

# Build and install the user-space from source
WORKDIR /app/linux-gpib-git/linux-gpib-user
RUN ./bootstrap && \
    ./configure --sysconfdir=/etc && \
    make -j$(nproc) && \
    make install && \
    ldconfig

# # Go back to the application directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]