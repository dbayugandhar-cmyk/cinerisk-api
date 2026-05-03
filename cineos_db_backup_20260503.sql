--
-- PostgreSQL database dump
--

\restrict oyW0CKxnccaMHECgd1h0A0uhxvdxS0ZidRHMibFygpUcJZh2KCL4EwZtgekbYVY

-- Dumped from database version 18.3 (Debian 18.3-1.pgdg13+1)
-- Dumped by pg_dump version 18.3 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: detection_sessions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.detection_sessions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    theater_name text,
    screen_number text,
    film_title text,
    zone text,
    started_at timestamp with time zone DEFAULT now(),
    last_seen_at timestamp with time zone DEFAULT now(),
    detection_count integer DEFAULT 1,
    max_confidence double precision,
    duration_seconds integer DEFAULT 0,
    escalation_level integer DEFAULT 1,
    resolved boolean DEFAULT false
);


ALTER TABLE public.detection_sessions OWNER TO postgres;

--
-- Name: incidents; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.incidents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    theater_name text,
    screen_number text,
    seat_location text,
    zone text,
    detection_type text DEFAULT 'PHONE'::text,
    confidence double precision,
    film_title text,
    alerted boolean DEFAULT false,
    device_id text,
    detected_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.incidents OWNER TO postgres;

--
-- Name: scan_results; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.scan_results (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    incident_id uuid,
    film_title text,
    scan_time timestamp with time zone DEFAULT now(),
    hits_found integer DEFAULT 0,
    platforms text[],
    first_hit_url text,
    gap_minutes integer,
    scan_query text
);


ALTER TABLE public.scan_results OWNER TO postgres;

--
-- Name: screenings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.screenings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    theater_name text,
    screen_number text,
    film_title text,
    genre text,
    release_strategy text,
    started_at timestamp with time zone DEFAULT now(),
    ended_at timestamp with time zone
);


ALTER TABLE public.screenings OWNER TO postgres;

--
-- Data for Name: detection_sessions; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.detection_sessions (id, theater_name, screen_number, film_title, zone, started_at, last_seen_at, detection_count, max_confidence, duration_seconds, escalation_level, resolved) FROM stdin;
f68fdb1a-b88f-4e5b-8dad-3ab548d1cd9e	Alamo Drafthouse	Screen 1	Mandalorian Grogu	CENTER	2026-05-03 11:29:28.128444+00	2026-05-03 11:29:28.128444+00	1	0.4226343035697937	0	1	f
7f771c1f-bd0c-49ce-97a2-8bdcd4dd2524	Alamo Drafthouse	Screen 1	Mandalorian Grogu	RIGHT	2026-05-03 11:29:33.898436+00	2026-05-03 11:29:33.898436+00	1	0.8036599159240723	0	1	f
7b29d919-5fd7-4ed2-9dd4-7ffea098afe8	Alamo Drafthouse	Screen 1	Mandalorian Grogu	CENTER	2026-05-03 11:32:11.401002+00	2026-05-03 11:32:11.401002+00	1	0.6912497878074646	0	1	f
5b0c9220-12d3-442d-83b1-9f81873304c2	Alamo Drafthouse	Screen 1	Mandalorian Grogu	LEFT	2026-05-03 11:32:19.27531+00	2026-05-03 11:32:19.27531+00	1	0.8334187269210815	0	1	f
7490e9a3-66a0-4982-9ef6-1ac9493dddb3	Alamo Drafthouse	Screen 1	Mandalorian Grogu	CENTER	2026-05-03 13:50:16.973954+00	2026-05-03 13:50:16.973954+00	1	0.8044342398643494	0	1	f
762f8d36-c0c5-4b58-ae13-a35f90b9cb12	Alamo Drafthouse	Screen 1	Mandalorian Grogu	LEFT	2026-05-03 13:50:21.139137+00	2026-05-03 13:50:21.139137+00	1	0.5561899542808533	0	1	f
613e45d6-46bf-4dd6-a931-88bdf60dba89	Alamo Drafthouse	Screen 1	Mandalorian Grogu	CENTER	2026-05-03 13:52:22.913114+00	2026-05-03 13:52:22.913114+00	1	0.8263916373252869	0	1	f
227fb2a7-6dee-4f42-8bab-c0873b8c43ed	Alamo Drafthouse	Screen 1	Mandalorian Grogu	LEFT	2026-05-03 13:52:24.48139+00	2026-05-03 13:52:24.48139+00	1	0.28827163577079773	0	1	f
70c5b4b3-c473-4b57-9049-79c90934269b	Alamo Drafthouse	Screen 1	Mandalorian Grogu	CENTER	2026-05-03 14:33:25.24928+00	2026-05-03 14:33:25.24928+00	1	0.6175178289413452	0	1	f
a9b7a88c-bd17-4059-b7ea-06a869b30ccf	Alamo Drafthouse	Screen 1	Mandalorian Grogu	LEFT	2026-05-03 14:33:27.145859+00	2026-05-03 14:33:27.145859+00	1	0.7048854231834412	0	1	f
bc3b2cc2-6e55-4274-bc05-04e96b61ab89	Alamo Drafthouse	Screen 1	Mandalorian Grogu	RIGHT	2026-05-03 14:34:59.321855+00	2026-05-03 14:34:59.321855+00	1	0.3986217677593231	0	1	f
f53aba68-875b-4f90-b5f3-5a5c707a5187	Alamo Drafthouse	Screen 1	Mandalorian Grogu	CENTER	2026-05-03 14:35:28.667529+00	2026-05-03 14:35:28.667529+00	1	0.5040781497955322	0	1	f
4ca951f9-2cfb-42f6-b2be-eeb90dec5e8f	Alamo Drafthouse	Screen 1	Mandalorian Grogu	RIGHT	2026-05-03 14:35:48.944336+00	2026-05-03 14:35:48.944336+00	1	0.39757341146469116	0	1	f
fd1c117a-30d1-4322-b7e2-5873787cc84d	Alamo Drafthouse	Screen 1	Mandalorian Grogu	CENTER	2026-05-03 14:40:37.903726+00	2026-05-03 14:40:37.903726+00	1	0.28261038661003113	0	1	f
66fc3126-8577-4ddc-866a-8c99da91d8fb	Alamo Drafthouse	Screen 1	Mandalorian Grogu	RIGHT	2026-05-03 14:40:39.787661+00	2026-05-03 14:40:39.787661+00	1	0.6844215989112854	0	1	f
\.


--
-- Data for Name: incidents; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.incidents (id, theater_name, screen_number, seat_location, zone, detection_type, confidence, film_title, alerted, device_id, detected_at) FROM stdin;
101d8392-3790-4ca3-bd7c-2882a5159b42	Alamo Drafthouse	Screen 1	\N	LEFT	PHONE	0.388	Mandalorian Grogu	f	cineos-rtsp-screen-1-1777807221	2026-05-03 11:20:22.144146+00
ba6434a9-f700-48a9-9fd4-05508b9ab88f	Alamo Drafthouse	Screen 1	\N	CENTER	PHONE	0.522	Mandalorian Grogu	t	cineos-rtsp-screen-1-1777807217	2026-05-03 11:20:18.228183+00
a8974f73-cf48-4e88-971c-50a6c2e7c3fe	Alamo Drafthouse	Screen 1	\N	CENTER	PHONE	0.559	Mandalorian Grogu	t	cineos-rtsp-screen-1-1777807709	2026-05-03 11:28:30.248717+00
3c1b5d48-e65f-4a10-b9a8-db41b105ec84	Alamo Drafthouse	Screen 1	\N	CENTER	PHONE	0.423	Mandalorian Grogu	f	cineos-rtsp-screen-1-1777807767	2026-05-03 11:29:27.352281+00
c0c52908-cef6-43ec-86f6-b7ce00be573f	Alamo Drafthouse	Screen 3	\N	CENTER	PHONE	0.85	Mandalorian Grogu	t	staff-web-1777794627997	2026-05-03 07:50:28.46418+00
1c306663-38f8-4149-8e4c-7e44883bdf4e	Alamo Drafthouse	Screen 3	\N	CENTER	PHONE	0.85	Mandalorian Grogu	t	staff-web-1777796299583	2026-05-03 08:18:20.022968+00
f8cf1952-682f-4946-b469-6cfa9fbac028	Alamo Drafthouse	Screen 3	\N	RIGHT	PHONE	0.85	Mandalorian Grogu	t	staff-web-1777796303581	2026-05-03 08:18:23.728334+00
41eb318b-f26d-4b41-aaf5-1eb3bc59c1e3	Alamo Drafthouse	Screen 3	\N	LEFT	PHONE	0.85	Mandalorian Grogu	t	staff-web-1777796322725	2026-05-03 08:18:42.87633+00
c56623b7-9da6-47eb-8105-bc9428c3c5d2	Alamo Drafthouse	Screen 3	\N	CENTER	PHONE	0.85	Mandalorian Grogu	t	staff-web-1777796324770	2026-05-03 08:18:44.919451+00
7d8de5e6-dfab-4515-acee-5ee92a5c8d86	Cinemark Houston	Screen 4	Row D Seat 3	LEFT	PHONE	0.71	Mandalorian Grogu	t	\N	2026-05-03 10:03:55.633167+00
01c0104f-da0a-4d9f-bdd5-1c50443a023c	Regal LA Live	Screen 2	Row H Seat 9	RIGHT	PHONE	0.82	Mandalorian Grogu	t	\N	2026-05-03 10:03:49.240615+00
c7a0a84b-c47e-4bf5-9549-9711cab7cacb	AMC Empire 25	Screen 7	Row F Seat 12	CENTER	PHONE	0.78	Mandalorian Grogu	t	\N	2026-05-03 10:03:41.490047+00
88a4adc4-fcc7-4558-bc3b-7a0692184b68	Demo Theater	Screen 6	\N	CENTER	PHONE	0.75	Mandalorian Grogu	t	cineos-app-1777804706267	2026-05-03 10:38:26.407765+00
090bb243-2916-4031-96b7-6738cc50a4db	Demo Theater	Screen 3	\N	CENTER	CAMCORDER	0.75	Mandalorian Grogu	t	cineos-app-1777804664794	2026-05-03 10:37:45.154229+00
fb620d61-0dc1-43be-a666-1c3b0d49d7e3	Alamo Drafthouse	Screen 1	\N	LEFT	PHONE	0.833	Mandalorian Grogu	t	cineos-rtsp-screen-1-1777807938	2026-05-03 11:32:18.407522+00
9dff4323-f009-41ff-9216-b3820dcd865d	Alamo Drafthouse	Screen 1	\N	CENTER	PHONE	0.691	Mandalorian Grogu	t	cineos-rtsp-screen-1-1777807930	2026-05-03 11:32:10.556678+00
cee35060-6c82-4983-829a-8e80cefea1db	Alamo Drafthouse	Screen 1	\N	RIGHT	PHONE	0.804	Mandalorian Grogu	t	cineos-rtsp-screen-1-1777807772	2026-05-03 11:29:33.073848+00
7564017a-29a6-4fee-b3f5-a130cde12d07	Test Auth	Screen 1	\N	CENTER	PHONE	0.8	Auth Test	t	\N	2026-05-03 12:19:49.609042+00
873fb509-2cfb-4a65-b6cc-5a9426271124	Alamo Drafthouse	Screen 1	\N	LEFT	PHONE	0.288	Mandalorian Grogu	f	cineos-rtsp-screen-1-1777816343	2026-05-03 13:52:23.70196+00
ef9755ae-d3dd-450e-a8ed-f53d0bf9c7eb	Alamo Drafthouse	Screen 1	\N	CENTER	PHONE	0.826	Mandalorian Grogu	t	cineos-rtsp-screen-1-1777816341	2026-05-03 13:52:22.152718+00
cc1e1347-d003-40c0-936a-4b0dc091b7be	Alamo Drafthouse	Screen 1	\N	RIGHT	PHONE	0.399	Mandalorian Grogu	f	cineos-rtsp-screen-1-1777818898	2026-05-03 14:34:58.559629+00
df0de520-fabb-463b-b301-012891f0b9b7	Alamo Drafthouse	Screen 1	\N	RIGHT	PHONE	0.398	Mandalorian Grogu	f	cineos-rtsp-screen-1-1777818947	2026-05-03 14:35:48.184675+00
d6c43198-e03d-4a19-a1c5-40b20d358518	Alamo Drafthouse	Screen 1	\N	CENTER	PHONE	0.504	Mandalorian Grogu	t	cineos-rtsp-screen-1-1777818927	2026-05-03 14:35:27.907059+00
d045fe56-56cf-4d81-bd56-77d254e176c3	Alamo Drafthouse	Screen 1	\N	LEFT	PHONE	0.705	Mandalorian Grogu	t	cineos-rtsp-screen-1-1777818806	2026-05-03 14:33:26.330631+00
e2184608-7d7b-4894-8330-249f129ff080	Alamo Drafthouse	Screen 1	\N	CENTER	PHONE	0.283	Mandalorian Grogu	f	cineos-rtsp-screen-1-1777819235	2026-05-03 14:40:36.266817+00
e0f266c7-208f-4fb3-bff1-76275bdd1d90	Alamo Drafthouse	Screen 1	\N	RIGHT	PHONE	0.684	Mandalorian Grogu	t	cineos-rtsp-screen-1-1777819238	2026-05-03 14:40:38.86901+00
91ae4ea9-d465-44cf-8276-cdff1d61bd06	Alamo Drafthouse	Screen 1	\N	CENTER	PHONE	0.618	Mandalorian Grogu	t	cineos-rtsp-screen-1-1777818803	2026-05-03 14:33:23.589485+00
\.


--
-- Data for Name: scan_results; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.scan_results (id, incident_id, film_title, scan_time, hits_found, platforms, first_hit_url, gap_minutes, scan_query) FROM stdin;
aecbc9cc-3cc0-431c-9f01-243835f4a916	15d749b8-f19a-4d0f-824f-01d3af96358e	Nova Station	2026-05-03 07:43:49.105081+00	1	{whereyouwatch.com}	https://whereyouwatch.com/movies/nova-station/	335	"Nova Station" CAM torrent download
c6b6e8a2-0c51-4234-acee-a6a815f36984	f4476c99-1b65-4be2-9ab5-088d9c69fb4a	Nova Station	2026-05-03 07:43:49.42094+00	1	{whereyouwatch.com}	https://whereyouwatch.com/movies/nova-station/	334	"Nova Station" CAM torrent download
\.


--
-- Data for Name: screenings; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.screenings (id, theater_name, screen_number, film_title, genre, release_strategy, started_at, ended_at) FROM stdin;
\.


--
-- Name: detection_sessions detection_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.detection_sessions
    ADD CONSTRAINT detection_sessions_pkey PRIMARY KEY (id);


--
-- Name: incidents incidents_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.incidents
    ADD CONSTRAINT incidents_pkey PRIMARY KEY (id);


--
-- Name: scan_results scan_results_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.scan_results
    ADD CONSTRAINT scan_results_pkey PRIMARY KEY (id);


--
-- Name: screenings screenings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.screenings
    ADD CONSTRAINT screenings_pkey PRIMARY KEY (id);


--
-- Name: idx_inc_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_inc_at ON public.incidents USING btree (detected_at DESC);


--
-- Name: idx_inc_film; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_inc_film ON public.incidents USING btree (film_title);


--
-- Name: idx_incidents_alerted; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_incidents_alerted ON public.incidents USING btree (alerted);


--
-- Name: idx_incidents_film; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_incidents_film ON public.incidents USING btree (film_title);


--
-- Name: idx_incidents_theater; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_incidents_theater ON public.incidents USING btree (theater_name);


--
-- Name: idx_incidents_zone; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_incidents_zone ON public.incidents USING btree (zone);


--
-- Name: idx_scan_film; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_scan_film ON public.scan_results USING btree (film_title, scan_time DESC);


--
-- PostgreSQL database dump complete
--

\unrestrict oyW0CKxnccaMHECgd1h0A0uhxvdxS0ZidRHMibFygpUcJZh2KCL4EwZtgekbYVY

