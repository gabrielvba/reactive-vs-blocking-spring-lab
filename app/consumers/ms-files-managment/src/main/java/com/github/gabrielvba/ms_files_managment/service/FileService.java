package com.github.gabrielvba.ms_files_managment.service;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.InputStreamResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.io.IOException;
import java.io.InputStream;
import java.util.Objects;

@Service
public class FileService {

	private static final Logger logger = LoggerFactory.getLogger(FileService.class);

	private final RestClient restClient;
	private final String baseUrl;
	private final Timer producerFetchDuration;
	private final Counter imageProcessedBytesTotal;
	private final MeterRegistry meterRegistry;

	public FileService(
			@Value("${file.service.base-url}") String baseUrl,
			RestClient.Builder restClientBuilder,
			MeterRegistry meterRegistry
	) {
		this.baseUrl = Objects.requireNonNull(baseUrl, "file.service.base-url must not be null");
		this.restClient = restClientBuilder.baseUrl(this.baseUrl).build();
		this.meterRegistry = meterRegistry;

		this.producerFetchDuration = Timer.builder("producer.fetch.duration.seconds")
				.description("Latency of the producer fetch call")
				.publishPercentileHistogram()
				.register(meterRegistry);

		this.imageProcessedBytesTotal = Counter.builder("image.processed.bytes.total")
				.description("Total bytes processed")
				.register(meterRegistry);
	}

	/**
	 * Increments {@code imageProcessedBytesTotal} for every byte read from the producer stream
	 * (chunked responses and missing Content-Length are supported).
	 */
	private InputStream meterProducerStream(InputStream source) {
		return new InputStream() {
			@Override
			public int read() throws IOException {
				int b = source.read();
				if (b >= 0) {
					imageProcessedBytesTotal.increment();
				}
				return b;
			}

			@Override
			public int read(byte[] b, int off, int len) throws IOException {
				int n = source.read(b, off, len);
				if (n > 0) {
					imageProcessedBytesTotal.increment(n);
				}
				return n;
			}

			@Override
			public void close() throws IOException {
				source.close();
			}
		};
	}

	public ResponseEntity<Resource> getFileAsBase64Stream(String id) {
		logger.info("Fetching file '{}' as Base64 (streaming) from producer", id);

		Timer.Sample sample = Timer.start(this.meterRegistry);
		ResponseEntity<Resource> producerResponse;
		try {
			producerResponse = restClient.get()
					.uri("/image/base64/{id}", id)
					.retrieve()
					.toEntity(Resource.class);
		} catch (RuntimeException ex) {
			sample.stop(producerFetchDuration);
			throw ex;
		}
		sample.stop(producerFetchDuration);

		Resource producerBody = producerResponse.getBody();
		if (producerBody == null) {
			throw new IllegalStateException("Producer returned empty body for id: " + id);
		}

		InputStream inputStream;
		try {
			inputStream = meterProducerStream(producerBody.getInputStream());
		} catch (IOException ex) {
			throw new IllegalStateException("Unable to obtain stream from producer response", ex);
		}

		InputStreamResource streamingResource = new InputStreamResource(inputStream) {
			@Override
			public long contentLength() {
				long length = producerResponse.getHeaders().getContentLength();
				return length >= 0 ? length : -1;
			}
		};

		HttpHeaders headers = new HttpHeaders();
		headers.setContentType(MediaType.APPLICATION_JSON);

		return ResponseEntity.status(producerResponse.getStatusCode())
				.headers(headers)
				.body(streamingResource);
	}

	public ResponseEntity<Resource> getFileAsImageStream(String id) {
		logger.info("Fetching file '{}' as raw image (streaming)", id);

		Timer.Sample sample = Timer.start(this.meterRegistry);
		ResponseEntity<Resource> producerResponse;
		try {
			producerResponse = restClient.get()
					.uri("/image/raw/{id}", id)
					.retrieve()
					.toEntity(Resource.class);
		}
		catch (RuntimeException ex) {
			sample.stop(producerFetchDuration);
			throw ex;
		}
		sample.stop(producerFetchDuration);

		Resource producerBody = producerResponse.getBody();
		if (producerBody == null) {
			throw new IllegalStateException("Producer returned empty body for id: " + id);
		}

		InputStream inputStream;
		try {
			inputStream = meterProducerStream(producerBody.getInputStream());
		}
		catch (IOException ex) {
			throw new IllegalStateException("Unable to obtain stream from producer response", ex);
		}

		InputStreamResource streamingResource = new InputStreamResource(inputStream) {
			@Override
			public long contentLength() {
				long length = producerResponse.getHeaders().getContentLength();
				return length >= 0 ? length : -1;
			}

			@Override
			public String getFilename() {
				var disposition = producerResponse.getHeaders().getContentDisposition();
				return disposition != null ? disposition.getFilename() : null;
			}
		};

		HttpHeaders headers = new HttpHeaders();
		headers.putAll(producerResponse.getHeaders());

		// Evita duplicar Transfer-Encoding / Content-Length em streams chunked
		headers.remove(HttpHeaders.TRANSFER_ENCODING);
		headers.remove(HttpHeaders.CONTENT_LENGTH);

		if (headers.getContentDisposition() == null || headers.getContentDisposition().getFilename() == null) {
			headers.setContentDisposition(org.springframework.http.ContentDisposition.inline()
					.filename(id)
					.build());
		}

		if (headers.getContentType() == null) {
			headers.setContentType(resolveMediaType(headers.getContentDisposition().getFilename()));
		}

		return ResponseEntity.status(producerResponse.getStatusCode())
				.headers(headers)
				.body(streamingResource);
	}

	private MediaType resolveMediaType(String filename) {
		if (filename == null) {
			return MediaType.APPLICATION_OCTET_STREAM;
		}
		String lower = filename.toLowerCase();
		if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) {
			return MediaType.IMAGE_JPEG;
		}
		if (lower.endsWith(".png")) {
			return MediaType.IMAGE_PNG;
		}
		if (lower.endsWith(".gif")) {
			return MediaType.IMAGE_GIF;
		}
		return MediaType.APPLICATION_OCTET_STREAM;
	}
}
