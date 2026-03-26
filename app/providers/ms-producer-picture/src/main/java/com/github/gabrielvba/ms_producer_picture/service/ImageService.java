package com.github.gabrielvba.ms_producer_picture.service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.Map;
import java.util.LinkedHashSet;
import java.util.Objects;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ThreadLocalRandom;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.core.io.ResourceLoader;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import com.github.gabrielvba.ms_producer_picture.config.ImageProperties;

import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import jakarta.annotation.PostConstruct;

@Service
public class ImageService {

	private static final Logger logger = LoggerFactory.getLogger(ImageService.class);
	private static final String BASE64_EXTENSION = ".base64";

	private final ImageProperties imageProperties;
	private final ResourceLoader resourceLoader;
	private final boolean delayEnabled;
	private final long delayMaxMillis;
	private final MeterRegistry meterRegistry;

	private final Map<String, CachedImage> binaryCache = new ConcurrentHashMap<>();
	private final Map<String, CachedJsonResponse> base64Cache = new ConcurrentHashMap<>();

	public ImageService(ImageProperties imageProperties,
			ResourceLoader resourceLoader,
			@Value("${producer.simulation.delay-enabled:false}") boolean delayEnabled,
			@Value("${producer.simulation.delay-ms:0}") long delayMaxMillis,
			MeterRegistry meterRegistry) {
		this.imageProperties = imageProperties;
		this.resourceLoader = resourceLoader;
		this.delayEnabled = delayEnabled;
		this.delayMaxMillis = Math.max(delayMaxMillis, 0);
		this.meterRegistry = meterRegistry;

		// Register cache size metrics
		Gauge.builder("image.cache.size.bytes", binaryCache, this::calculateCacheSize)
			.description("Total size of cached images in bytes")
			.register(meterRegistry);

		Gauge.builder("image.cache.entries", binaryCache, Map::size)
			.description("Number of images in binary cache")
			.register(meterRegistry);

		Gauge.builder("image.cache.base64.entries", base64Cache, Map::size)
			.description("Number of images in base64 cache")
			.register(meterRegistry);
	}

	@PostConstruct
	public void preloadCaches() throws IOException {
		Timer.Sample sample = Timer.start(meterRegistry);
		logger.info("Preloading image caches (delayEnabled={}, delayMaxMillis={}ms)", delayEnabled, delayMaxMillis);

		Map<String, String> binaryMap = imageProperties.getBinary();
		Map<String, String> base64Map = imageProperties.getBase64();

		Set<String> keys = new LinkedHashSet<>();
		if (binaryMap != null) {
			keys.addAll(binaryMap.keySet());
		}
		if (base64Map != null) {
			keys.addAll(base64Map.keySet());
		}

		for (String key : keys) {
			Resource binaryResource = getResource(binaryMap, key);
			Resource base64Resource = getResource(base64Map, key);

			CachedImage cachedImage = null;
			CachedJsonResponse cachedBase64 = null;

			if (binaryResource != null && binaryResource.exists()) {
				cachedImage = loadBinary(binaryResource);
			}

			if (base64Resource != null && base64Resource.exists()) {
				cachedBase64 = loadBase64AsJson(base64Resource,
						cachedImage != null ? cachedImage.filename() : deriveFilenameFromBase64Resource(base64Resource));

				if (cachedImage == null) {
					byte[] decoded = Base64.getDecoder().decode(cachedBase64.base64());
					cachedImage = new CachedImage(decoded, cachedBase64.filename(),
							resolveMediaType(cachedBase64.filename()));
				}
			}

			if (cachedImage != null && cachedBase64 == null) {
				String base64 = Base64.getEncoder().encodeToString(cachedImage.bytes());
				byte[] jsonPayload = buildJsonPayload(base64, cachedImage.filename(), cachedImage.bytes().length);
				cachedBase64 = new CachedJsonResponse(base64, jsonPayload, cachedImage.filename(), cachedImage.bytes().length);
			}

			if (cachedImage != null) {
				binaryCache.put(key, cachedImage);
			}
			if (cachedBase64 != null) {
				base64Cache.put(key, cachedBase64);
			}

			if (cachedImage == null || cachedBase64 == null) {
				logger.warn("Key '{}' was only partially cached (binary={}, base64={})", key,
						cachedImage != null, cachedBase64 != null);
			}
		}

		logger.info("Producer cache ready: {} binary entries, {} base64 entries",
				binaryCache.size(), base64Cache.size());

		sample.stop(Timer.builder("image.cache.load.duration")
				.description("Time to load all images into cache at startup")
				.register(meterRegistry));
	}

	public CachedJsonResponse getBase64Image(String key) throws IOException {
		maybeDelay();
		CachedJsonResponse cached = base64Cache.get(key);
		if (cached == null) {
			meterRegistry.counter("image.cache.misses", "type", "base64", "key", key).increment();
			throw new ImageNotFoundException(key);
		}
		meterRegistry.counter("image.cache.hits", "type", "base64", "key", key).increment();
		return cached;
	}

	public BinaryImage getBinaryImage(String key) throws IOException {
		maybeDelay();
		CachedImage cached = binaryCache.get(key);
		if (cached == null) {
			meterRegistry.counter("image.cache.misses", "type", "binary", "key", key).increment();
			throw new ImageNotFoundException(key);
		}
		meterRegistry.counter("image.cache.hits", "type", "binary", "key", key).increment();
		return new BinaryImage(cached.bytes(), cached.filename(), cached.bytes().length, cached.mediaType());
	}

	public BinaryImageStream getBinaryImageAsStream(String key) throws IOException {
		BinaryImage image = getBinaryImage(key);
		return new BinaryImageStream(
				new java.io.ByteArrayInputStream(image.bytes()),
				image.filename(),
				image.sizeBytes(),
				image.mediaType()
		);
	}

	public record ImageResponse(String base64, String filename, long sizeBytes) {
	}

	public record BinaryImage(byte[] bytes, String filename, long sizeBytes, MediaType mediaType) {
	}

	public record BinaryImageStream(java.io.InputStream stream, String filename, long sizeBytes, MediaType mediaType) {
	}

	public static class ImageNotFoundException extends RuntimeException {
		public ImageNotFoundException(String key) {
			super("Image not found for key: " + key);
		}
	}

	private Resource getResource(Map<String, String> map, String key) {
		if (map == null) {
			return null;
		}
		String location = map.get(key);
		if (!StringUtils.hasText(location)) {
			return null;
		}
		String path = location.trim();
		if (!StringUtils.hasText(path)) {
			return null;
		}
		return resourceLoader.getResource(Objects.requireNonNull(path));
	}

	private CachedImage loadBinary(Resource resource) throws IOException {
		byte[] bytes;
		try (var inputStream = resource.getInputStream()) {
			bytes = inputStream.readAllBytes();
		}
		String filename = resource.getFilename();
		return new CachedImage(bytes, filename, resolveMediaType(filename));
	}

	private CachedJsonResponse loadBase64AsJson(Resource resource, String fallbackFilename) throws IOException {
		String content;
		try (var inputStream = resource.getInputStream()) {
			content = new String(inputStream.readAllBytes(), StandardCharsets.UTF_8);
		}
		String sanitized = sanitizeBase64(content);
		byte[] decoded = Base64.getDecoder().decode(sanitized);
		String filename = StringUtils.hasText(fallbackFilename)
				? fallbackFilename
				: deriveFilenameFromBase64Resource(resource);
		
		byte[] jsonPayload = buildJsonPayload(sanitized, filename, decoded.length);
		return new CachedJsonResponse(sanitized, jsonPayload, filename, decoded.length);
	}

	private byte[] buildJsonPayload(String base64, String filename, long sizeBytes) {
		String json = String.format("{\"base64\":\"%s\",\"filename\":\"%s\",\"sizeBytes\":%d}",
				base64, filename, sizeBytes);
		return json.getBytes(StandardCharsets.UTF_8);
	}

	private String deriveFilenameFromBase64Resource(Resource resource) {
		String rawName = resource.getFilename();
		if (!StringUtils.hasText(rawName)) {
			return resource.getDescription();
		}
		String filename = Objects.requireNonNull(rawName);
		if (filename.endsWith(BASE64_EXTENSION)) {
			filename = filename.substring(0, filename.length() - BASE64_EXTENSION.length());
		}
		return filename;
	}

	private MediaType resolveMediaType(String filename) {
		if (!StringUtils.hasText(filename)) {
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
		if (lower.endsWith(".bmp")) {
			return MediaType.valueOf("image/bmp");
		}
		return MediaType.APPLICATION_OCTET_STREAM;
	}

	private String sanitizeBase64(String value) {
		return value == null ? "" : value.replaceAll("\\s+", "");
	}

	private void maybeDelay() {
		if (!delayEnabled || delayMaxMillis <= 0) {
			return;
		}
		long candidate = ThreadLocalRandom.current().nextLong(delayMaxMillis + 1);
		if (candidate <= 0) {
			return;
		}
		try {
			Thread.sleep(candidate);
		}
		catch (InterruptedException ex) {
			Thread.currentThread().interrupt();
		}
	}

	private long calculateCacheSize(Map<String, CachedImage> cache) {
		return cache.values().stream()
				.mapToLong(img -> img.bytes().length)
				.sum();
	}

	private record CachedImage(byte[] bytes, String filename, MediaType mediaType) {
	}

	public record CachedJsonResponse(String base64, byte[] jsonBytes, String filename, long sizeBytes) {
	}
}
